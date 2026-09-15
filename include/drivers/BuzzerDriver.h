#pragma once

class BuzzerDriver {
public:
    void begin();
    void start();
    void stop();
    void update();
    bool isActive() const { return active_; }
private:
    bool active_ = false;
    unsigned long startedAt_ = 0;
};
