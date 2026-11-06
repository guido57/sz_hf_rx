# Native Linux build, including Xillinux on Cortex-A9.
CC       ?= gcc
CXX      ?= g++
LOG_LEVEL ?= LOG_ERROR
CPPFLAGS ?= -Isrc -DNATIVE_BUILD -DLOG_LEVEL=$(LOG_LEVEL)
CFLAGS   ?= -O3 -std=gnu11
CXXFLAGS ?= -O3 -std=gnu++17
LDLIBS   ?= -lm -latomic

TARGET := ft8_decoder
BUILD  := build/native

C_SOURCES := $(wildcard src/ft8/*.c src/fft/*.c) src/common/wave.c
CXX_SOURCES := src/main.cpp src/decoder_api.cpp src/decode_ft8.cpp src/subtract.cpp src/native_osd.cpp
OBJECTS := $(C_SOURCES:src/%.c=$(BUILD)/%.o) \
           $(CXX_SOURCES:src/%.cpp=$(BUILD)/%.o)

# SmartZynq live PCM receiver build.
STREAM_BUILD := build/a9-stream
STREAM_TARGET := $(STREAM_BUILD)/ft8-subtract-stream-a9
STREAM_CPPFLAGS := -Isrc -DNATIVE_BUILD -DLOG_LEVEL=LOG_INFO -DFT8_MAX_CANDIDATES=80
STREAM_CFLAGS := -O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=gnu11
STREAM_CXXFLAGS := -O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=gnu++17
STREAM_C_SOURCES := src/fft/kiss_fft.c src/fft/kiss_fftr.c \
                    src/ft8/constants.c src/ft8/crc.c src/ft8/decode.c \
                    src/ft8/encode.c src/ft8/ldpc.c src/ft8/message.c \
                    src/ft8/pack.c src/ft8/text.c src/ft8/unpack.c
STREAM_CXX_SOURCES := src/ft8_subtract_stream.cpp src/decoder_api.cpp \
                      src/decode_ft8.cpp src/subtract.cpp src/native_osd.cpp
STREAM_OBJECTS := $(STREAM_C_SOURCES:%.c=$(STREAM_BUILD)/%.o) \
                  $(STREAM_CXX_SOURCES:%.cpp=$(STREAM_BUILD)/%.o)

.PHONY: all clean a9 stream stream-clean

ifeq ($(DIAGNOSTIC),1)
CPPFLAGS += -DNATIVE_DIAGNOSTIC=1
endif

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) -o $@ $^ $(LDLIBS)

$(BUILD)/%.o: src/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD)/%.o: src/%.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD) $(TARGET)

# Native decoder optimized for the Xillinux Cortex-A9.
A9_CFLAGS := -O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=gnu11
A9_CXXFLAGS := -O3 -mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard -std=gnu++17
a9: clean
	$(MAKE) CPPFLAGS='-Isrc -DNATIVE_BUILD -DLOG_LEVEL=LOG_INFO -DFT8_MAX_CANDIDATES=80' CFLAGS='$(A9_CFLAGS)' CXXFLAGS='$(A9_CXXFLAGS)' all

# Live PCM capture with three-pass residual subtraction.
stream: $(STREAM_TARGET)

$(STREAM_TARGET): $(STREAM_OBJECTS)
	$(CXX) -o $@ $^ $(LDLIBS) -pthread

$(STREAM_BUILD)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(STREAM_CPPFLAGS) $(STREAM_CFLAGS) -c $< -o $@

$(STREAM_BUILD)/%.o: %.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(STREAM_CPPFLAGS) $(STREAM_CXXFLAGS) -c $< -o $@

stream-clean:
	rm -rf $(STREAM_BUILD)
