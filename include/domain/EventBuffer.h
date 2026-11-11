#pragma once
#include <stddef.h>
#include <stdint.h>

// Fixed-capacity volatile FIFO. Overflow drops the oldest event and counts the loss.
template <typename T, size_t Capacity> class EventBuffer {
public:
    void push(const T& item) {
        if (count_ == Capacity) { pop(); ++dropped_; }
        items_[(head_ + count_) % Capacity] = item; ++count_;
    }
    const T& front() const { return items_[head_]; }
    void pop() { if (count_) { head_ = (head_ + 1) % Capacity; --count_; } }
    size_t size() const { return count_; }
    uint32_t dropped() const { return dropped_; }
private:
    T items_[Capacity]{};
    size_t head_ = 0, count_ = 0;
    uint32_t dropped_ = 0;
};
