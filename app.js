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
    sendMsg(io, 'rtweight', ready);
    //io.emit("data", data);
});
/*********************************************** */
//Socket.io
io.on('connection', socket => {
    console.log('Usuario conectado');

    // Maneja el evento de mensaje
    socket.on('rtweight', msg => {
        console.log('Mensaje recibido: ' + msg);
        // Emite el mensaje a todos los clientes conectados
        io.emit('rtweight', msg);
    });

    // Maneja el evento de desconexión
    socket.on('disconnect', () => {
        console.log('Usuario desconectado');
    });
});

const sendMsg = (io, event, mensaje) => { // Agregar 'event' como un parámetro adicional
    io.emit(event, mensaje);
};


app.listen(PORT, () => {
    console.log(`Running on ${PORT}`);
});
