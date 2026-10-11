
for(;;) { if(globalFlag) {} }
class A {
    run() { for(;;){for(;;){if(a){if(b){}}}} }
}
function outer() {
    if(a) {
        function inner() { for(;;){while(b){if(c){}}} }
        const anonymous = () => { while(a){if(b){}} };
    }
}
function empty() {}
