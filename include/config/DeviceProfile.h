#pragma once
#if __has_include("config/Secrets.h")
#include "config/Secrets.h"
#endif
#ifndef PILLBOX_SCHEDULE_PREFIX
#define PILLBOX_SCHEDULE_PREFIX ""
#endif

static_assert(sizeof(PILLBOX_SCHEDULE_PREFIX)<=34,"Schedule prefix must be at most 33 characters");
