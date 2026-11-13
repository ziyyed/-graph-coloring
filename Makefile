CC := gcc
CFLAGS := -std=c11 -O2 -Wall -Wextra -Wpedantic -fopenmp
LDFLAGS := -fopenmp
BUILD_DIR := build
SOURCE := src/coloring.c

ifeq ($(OS),Windows_NT)
TARGET := $(BUILD_DIR)/coloring.exe
MKDIR_BUILD = if not exist $(BUILD_DIR) mkdir $(BUILD_DIR)
REMOVE_BUILD = rmdir /S /Q $(BUILD_DIR)
else
TARGET := $(BUILD_DIR)/coloring
MKDIR_BUILD = mkdir -p $(BUILD_DIR)
REMOVE_BUILD = rm -rf $(BUILD_DIR)
endif

.PHONY: all clean test graphs benchmark report slides

all: $(TARGET)

$(TARGET): $(SOURCE)
	@$(MKDIR_BUILD)
	$(CC) $(CFLAGS) $(SOURCE) -o $(TARGET) $(LDFLAGS)

clean:
	$(REMOVE_BUILD)

test: $(TARGET)
	python tests/test_color.py

graphs:
	python scripts/generate_graphs.py

benchmark: $(TARGET)
	python scripts/benchmark.py
