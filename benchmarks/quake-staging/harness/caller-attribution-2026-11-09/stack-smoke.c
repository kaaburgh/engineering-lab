#include <stdint.h>
#include <stdio.h>
__attribute__((noinline)) static uint64_t spin(void){volatile uint64_t a=0;for(uint64_t i=0;i<1000000000ULL;i++)a+=i;return a;}
__attribute__((noinline)) static uint64_t caller(void){return spin()+1;}
int main(void){printf("%llu\n",(unsigned long long)caller());return 0;}
