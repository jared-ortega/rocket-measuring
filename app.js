const express = require('express');
const http = require('http'); 
const socketIo = require('socket.io'); //socketio
const app = express();
const PORT = process.env.PORT || 3000;
const path = require('path'); 
// Set up server
const server = http.createServer(app);
const io = socketIo(server);

let rtw = 0;

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

//new amazing serial connection
const {SerialPort } = require("serialport");
const {DelimiterParser} = require('@serialport/parser-delimiter');
const port = new SerialPort({
    path: 'COM3',
    baudRate: 9600,
  });
//parser:
const parser = port.pipe(new DelimiterParser({delimiter: '\n'}));
parser.on('open', function () {
    console.log("Connection is open");
});
parser.on('data', function(data){
    let enc = new TextDecoder();
    let arr = new Uint8Array(data);
    let ready = enc.decode(arr)
    console.log("Input: ", ready);
    //io.emit("data", data);
});
/*********************************************** */
//Socket.io



app.listen(PORT, () => {
    console.log(`Running on ${PORT}`);
});
