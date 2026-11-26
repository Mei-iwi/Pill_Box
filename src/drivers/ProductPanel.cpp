#include "drivers/ProductPanel.h"
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Keypad.h>

static Adafruit_SSD1306 oled(128,64,&Wire,-1);
static char keys[4][4]={{'1','2','3','A'},{'4','5','6','B'},{'7','8','9','C'},{'*','0','#','D'}};
static byte rows[4]={15,16,17,18};
static byte columns[4]={21,33,34,35};
static Keypad keypad(makeKeymap(keys),rows,columns,4,4);

void ProductPanel::begin() {
    // Wire is initialized by RtcDriver; keep the same SDA=3/SCL=4 bus.
    displayReady_=oled.begin(SSD1306_SWITCHCAPVCC,0x3C,true,false);
    Serial1.begin(9600,SERIAL_8N1,13,14);
    if(displayReady_){oled.clearDisplay();oled.display();}
}
void ProductPanel::character(char c) {
    if(c=='\r'||c=='\n'||c=='#') {
        if(length_>=4&&!invalidInput_){strlcpy(ready_,input_,sizeof(ready_));strlcpy(captured_,input_,sizeof(captured_));}
        else if(length_||invalidInput_)Serial.println("Barcode rejected: use 4-48 printable ASCII characters.");
        length_=0;input_[0]=0;invalidInput_=false;
    } else if(c=='*'||c=='\b') {
        if(length_)input_[--length_]=0;
    } else if(c>=32&&c<=126&&length_<sizeof(input_)-1){input_[length_++]=c;input_[length_]=0;}
    else invalidInput_=true;
}
bool ProductPanel::takeScan(char* destination,unsigned capacity) {
    if(!ready_[0])return false;
    strlcpy(destination,ready_,capacity);ready_[0]=0;return true;
}
void ProductPanel::update(uint16_t minute,uint16_t second,const char* state,bool connected,const Schedule* schedules) {
    const char key=keypad.getKey();
    if(key>='A'&&key<='C')selected_=key-'A'+1;
    else if(key=='D'){length_=0;input_[0]=0;invalidInput_=false;}
    else if(key)character(key);
    unsigned budget=64;while(Serial1.available()&&budget--)character(Serial1.read());
    if(!displayReady_||millis()-lastDraw_<500)return;
    lastDraw_=millis();oled.clearDisplay();oled.setTextColor(SSD1306_WHITE);oled.setTextSize(2);oled.setCursor(0,0);
    char time[12];snprintf(time,sizeof(time),"%02u:%02u:%02u",minute/60,minute%60,second);oled.print(time);
    oled.setTextSize(1);oled.setCursor(0,20);oled.print(connected?"MQTT ONLINE ":"MQTT OFFLINE ");oled.print(state);
    oled.setCursor(0,31);oled.print("SLOT ");oled.print(selected_);
    for(unsigned i=0;i<4;++i)if(schedules[i].slotId==selected_){oled.print(" ");oled.print(schedules[i].medicationCode);break;}
    oled.setCursor(0,43);oled.print(length_?input_:captured_[0]?captured_:"SCAN: UART / KEYPAD");
    oled.setCursor(0,55);oled.print("# SEND * DEL A-C SLOT");oled.display();
}
