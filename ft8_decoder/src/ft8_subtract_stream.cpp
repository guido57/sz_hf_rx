/* Capture 15-second PCM16 slots with residual-subtraction FT8 decoding. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include "decoder_api.h"

enum { SAMPLE_RATE = 8000, SLOT_SECONDS = 15, SLOT_SAMPLES = 120000,
       BUFFER_COUNT = 2 };

struct slot_buffer {
    int16_t *samples;
    struct tm utc;
    double utc_fraction;
    bool ready;
};

struct capture_state {
    const char *device;
    int requested_slots;
    int produced;
    int failed;
    int fd;
    struct slot_buffer buffers[BUFFER_COUNT];
    pthread_mutex_t mutex;
    pthread_cond_t ready;
    pthread_cond_t free_buffer;
};

static void usage(const char *program) {
    fprintf(stderr, "Usage: %s [--device PATH] [--slots N] [--base-mhz MHz]\n", program);
}

static int parse_positive(const char *text) {
    char *end = NULL;
    long value = strtol(text, &end, 10);
    return (end && !*end && value > 0 && value <= 1000000) ? (int)value : 0;
}

static int parse_frequency(const char *text, float *value) {
    char *end = NULL;
    double parsed = strtod(text, &end);
    if (!end || *end || parsed <= 0.0 || parsed > 1000.0) return -1;
    *value = (float)parsed;
    return 0;
}

static int wait_until_next_slot(time_t *slot_start) {
    struct timespec now;
    time_t target;
    if (clock_gettime(CLOCK_REALTIME, &now)) return -1;
    target = now.tv_sec - (now.tv_sec % SLOT_SECONDS) + SLOT_SECONDS;
    {
        struct timespec deadline = { target, 0 };
        while (clock_nanosleep(CLOCK_REALTIME, TIMER_ABSTIME, &deadline, NULL) == EINTR) {}
    }
    *slot_start = target;
    return 0;
}

static int read_slot(int fd, int16_t *samples) {
    size_t remaining = SLOT_SAMPLES * sizeof(*samples);
    unsigned char *where = (unsigned char *)samples;
    while (remaining) {
        ssize_t bytes = read(fd, where, remaining > 16384 ? 16384 : remaining);
        if (bytes < 0 && errno == EINTR) continue;
        if (bytes <= 0) return -1;
        where += bytes;
        remaining -= (size_t)bytes;
    }
    return 0;
}

static void *capture_slots(void *opaque) {
    struct capture_state *state = (struct capture_state *)opaque;
    time_t slot_start;
    /* Opening the Xillybus stream starts its byte stream. Wait first so its
       FIFO cannot fill while waiting for the UTC boundary. */
    if (wait_until_next_slot(&slot_start)) {
        perror("FT8 UTC slot wait");
        state->failed = 1;
        pthread_cond_broadcast(&state->ready);
        return NULL;
    }
    state->fd = open(state->device, O_RDONLY);
    if (state->fd < 0) {
        perror(state->device);
        state->failed = 1;
        pthread_cond_broadcast(&state->ready);
        return NULL;
    }
    while (state->requested_slots == 0 || state->produced < state->requested_slots) {
        int index;
        struct slot_buffer *slot;
        pthread_mutex_lock(&state->mutex);
        while (state->buffers[state->produced % BUFFER_COUNT].ready)
            pthread_cond_wait(&state->free_buffer, &state->mutex);
        index = state->produced % BUFFER_COUNT;
        pthread_mutex_unlock(&state->mutex);
        slot = &state->buffers[index];
        gmtime_r(&slot_start, &slot->utc);
        slot->utc_fraction = 0.0;
        if (read_slot(state->fd, slot->samples)) {
            perror("FT8 PCM capture");
            pthread_mutex_lock(&state->mutex);
            state->failed = 1;
            pthread_cond_broadcast(&state->ready);
            pthread_mutex_unlock(&state->mutex);
            break;
        }
        slot_start += SLOT_SECONDS;
        pthread_mutex_lock(&state->mutex);
        slot->ready = true;
        ++state->produced;
        pthread_cond_signal(&state->ready);
        pthread_mutex_unlock(&state->mutex);
    }
    if (state->fd >= 0) close(state->fd);
    return NULL;
}

static int decode_slot(const struct slot_buffer *slot, float base_frequency_mhz) {
    ft8_decode_context_t context;
    ft8_stream_decoder_t *decoder;
    int rc;
    memset(&context, 0, sizeof(context));
    context.is_ft8 = true;
    context.base_freq_mhz = base_frequency_mhz;
    context.utc = slot->utc;
    context.utc_frac_sec = slot->utc_fraction;
    /* -1 selects automatic cancellation for every decoded candidate. */
    context.cand_to_subtract = -1;
    context.max_decode_passes = 3;
    decoder = ft8_stream_open(SAMPLE_RATE, &context);
    if (!decoder) return -1;
    rc = ft8_stream_append_i16(decoder, slot->samples, SLOT_SAMPLES);
    if (rc >= 0) rc = ft8_stream_finalize(decoder);
    ft8_stream_close(decoder);
    return rc;
}

int main(int argc, char **argv) {
    struct capture_state state;
    pthread_t producer;
    const char *device = "/dev/xillybus_read_8";
    float base_frequency_mhz = 14.074f;
    int slots = 1;
    int consumed = 0;
    int index;
    memset(&state, 0, sizeof(state));
    state.fd = -1;
    for (index = 1; index < argc; ++index) {
        if (!strcmp(argv[index], "--device") && index + 1 < argc) device = argv[++index];
        else if (!strcmp(argv[index], "--slots") && index + 1 < argc) {
            slots = parse_positive(argv[++index]);
            if (!slots) { usage(argv[0]); return 2; }
        } else if (!strcmp(argv[index], "--base-mhz") && index + 1 < argc) {
            if (parse_frequency(argv[++index], &base_frequency_mhz)) {
                usage(argv[0]);
                return 2;
            }
        } else { usage(argv[0]); return 2; }
    }
    state.device = device;
    state.requested_slots = slots;
    pthread_mutex_init(&state.mutex, NULL);
    pthread_cond_init(&state.ready, NULL);
    pthread_cond_init(&state.free_buffer, NULL);
    for (index = 0; index < BUFFER_COUNT; ++index) {
        state.buffers[index].samples =
            (int16_t *)malloc(SLOT_SAMPLES * sizeof(int16_t));
        if (!state.buffers[index].samples) return 1;
    }
    if (pthread_create(&producer, NULL, capture_slots, &state)) return 1;
    while (consumed < slots) {
        struct slot_buffer *slot;
        pthread_mutex_lock(&state.mutex);
        while (!state.failed && !state.buffers[consumed % BUFFER_COUNT].ready)
            pthread_cond_wait(&state.ready, &state.mutex);
        if (state.failed) { pthread_mutex_unlock(&state.mutex); break; }
        slot = &state.buffers[consumed % BUFFER_COUNT];
        pthread_mutex_unlock(&state.mutex);
        fprintf(stderr, "Decoding UTC %02d:%02d:%02d.%03d\n", slot->utc.tm_hour,
                slot->utc.tm_min, slot->utc.tm_sec,
                (int)(slot->utc_fraction * 1000.0));
        if (decode_slot(slot, base_frequency_mhz) < 0) state.failed = 1;
        pthread_mutex_lock(&state.mutex);
        slot->ready = false;
        pthread_cond_signal(&state.free_buffer);
        pthread_mutex_unlock(&state.mutex);
        ++consumed;
    }
    pthread_join(producer, NULL);
    for (index = 0; index < BUFFER_COUNT; ++index) free(state.buffers[index].samples);
    return state.failed ? 1 : 0;
}
