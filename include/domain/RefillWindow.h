#pragma once
#include <stdint.h>
#include <string.h>

// Time-bounded authorization. Uses UTC for expiry, independently of the demo RTC.
class RefillWindow {
public:
    bool begin(uint8_t slot, const char* id, uint32_t expires, uint32_t utc, uint32_t now) {
        if (slot<1 || slot>3 || !id || strlen(id)!=32 || utc<1704067200 ||
            expires<=utc || expires-utc>300) return false;
        for (const char* p=id;*p;++p) if (!((*p>='0' && *p<='9') || (*p>='a' && *p<='f'))) return false;
        if (!strcmp(id,id_)) return allows(slot,utc,now); // duplicate must not extend it
        if (allows(slot_,utc,now)) return false;
        strcpy(id_,id); slot_=slot; expires_=expires; started_=now;
        duration_=(expires-utc)*1000UL; active_=true; return true;
    }
    bool allows(uint8_t slot, uint32_t utc, uint32_t now) const {
        return active_ && slot==slot_ && utc>=1704067200 && utc<expires_ &&
            static_cast<uint32_t>(now-started_)<duration_;
    }
    bool end(const char* id) {
        if (!id || strcmp(id,id_)) return false;
        active_=false; return true;
    }
    const char* id() const { return id_; }
private:
    char id_[33]{};
    uint8_t slot_=0;
    bool active_=false;
    uint32_t expires_=0,started_=0,duration_=0;
};
