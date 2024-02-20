const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;
const path = require('path'); 

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Running on ${PORT}`);
});
/*********************************************** */
//new amazing serial connection
const {SerialPort } = require("serialport");
const {DelimiterParser} = require('@serialport/parser-delimiter');


console.log("serialport.list(): ",SerialPort.list());
// Create a port
const port = new SerialPort({
    path: 'COM3',
    baudRate: 9600,
  });

//   port.open(function (err) {
//     if (err) {
//       return console.log('******* Error opening port: ', err.message)
//     }
//     // Because there's no callback to write, write errors will be emitted on the port:
//     port.write('main screen turn on')
//   })

//parser:
const parser = port.pipe(new DelimiterParser({delimiter: '\n'}));

parser.on('open', function () {
    console.log("Connection is open");
});

parser.on('data', function(data){
    let enc = new TextDecoder();
    let arr = new Uint8Array(data);
    let ready = enc.decode(arr)
    console.log(ready);
});

// SerialPortMock.list();





//tuto code:

// const parsers = SerialPort.parsers;

// const parser = new parsers.Readline({
//   delimiter: "\r\n",
// });

// var port = new SerialPort("/dev/tty.wchusbserialfa1410", {
//     baudRate: 9600,
//     dataBits: 8,
//     parity: "none",
//     stopBits: 1,
//     flowControl: false,
//   });

//   port.pipe(parser);

//   var io = require("socket.io").listen(app);

// io.on("connection", function (socket) {
//   console.log("Node is listening to port");
// });

// parser.on("data", function (data) {
//   console.log("Received data from port: " + data);
//   io.emit("data", data);
// });
