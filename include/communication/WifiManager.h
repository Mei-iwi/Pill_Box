#pragma once

class WifiManager {
public:
    void begin();
    void update();
    bool connected() const;
private:
    unsigned long lastAttempt_ = 0;
    bool started_ = false;
};
