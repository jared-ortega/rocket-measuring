const {SerialPort } = require("serialport");
const {DelimiterParser} = require('@serialport/parser-delimiter');

// Create a port
const port = new SerialPort({
    path: 'COM3',
    baudRate: 9600,
  });

//parser:
const parser = port.pipe(new DelimiterParser({delimiter: '\n'}));

parser.on('open', function (data) {
    console.log("Connection is open");
});

parser.on('data', function(data){
    let enc = new TextDecoder();
    let arr = new Uint8Array(data);
    let ready = enc.decode(arr)
    console.log(ready);
});
