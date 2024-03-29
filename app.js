const express = require("express");
const http = require("http");
const { SerialPort } = require("serialport");
const socketIo = require("socket.io"); //socketio
const app = express();
const path = require("path");

const server = http.createServer(app);
const io = socketIo(server);

let telemetry = {
  timestamps: [],
  measurements: [],
};

let calibrationValue = 0.0; //valor tara

let dataArray = [];

//Este objeto guardara los resultados del test (tambien en un csv dentro del servidor)
let telemetryResult ={
  timestamps: [],
  measurements: [],
}

app.use(express.static(__dirname + "/public"));

app.get("/", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

app.use(
  "/socket.io",
  express.static(
    path.join(__dirname, "node_modules", "socket.io", "client-dist")
  )
);

//update telemtry
const updateTele = (measurement) => {
  //tomo objeto y lo actualizo
  const time = Date.now().toString();
  telemetry.timestamps.push(time);
  telemetry.measurements.push(measurement);
};

const clearTele = () => {
  telemetry.timestamps = [];
  telemetry.measurements = [];
};

const setTare = () => {
  let lastValue = telemetry.measurements[telemetry.measurements.length -1];
  calibrationValue = lastValue;
}

//start func
const initTest = () => {
  console.log("init test")
  //  Clear array

  //  delay

  //  init pin relay

  //
}



//new amazing serial connection
const { DelimiterParser } = require("@serialport/parser-delimiter");
const port = new SerialPort({
  path: "COM3",
  baudRate: 9600,
});
//parser:
const parser = port.pipe(new DelimiterParser({ delimiter: "\n" }));
parser.on("open", function () {
  console.log("Connection is open");
});
parser.on("data", function (data) {
  let enc = new TextDecoder();
  let arr = new Uint8Array(data);
  let ready = enc.decode(arr);
  //console.log("Input: ", ready);
  let value = ready.toString();
  let valueN = parseFloat(value) - calibrationValue;
  console.log("value: ", valueN);

  //updateTelemetry array
  updateTele(ready.toString());
  sendMsg(io, "rtweight", ready);
  console.log(telemetry);

});

//Socket.io
io.on("connection", (socket) => {
  console.log("Usuario conectado");
  // Maneja el evento de mensaje
  socket.on("rtweight", (msg) => {
    console.log("Mensaje recibido: " + msg);
    // Emite el mensaje a todos los clientes conectados
    io.emit("rtweight", msg);
  });

  // Mensaje desde el cliente:
  socket.on("serverInput", (msg)=>{
    switch(msg){
      case "tare":
        console.log("Entra el funcion tara");
        setTare();
        break;
      case "start":
        console.log("Entra en la funcion start");
        break;
      case "clear":
        console.log("Entra en la funcion clear");
        clearTele();
        break;
      case "save":
        console.log("Entra en la funcion save");
        break;
      default:
        console.log("Entra en default");
    }

  })

  // Evento de desconexión
  socket.on("disconnect", () => {
    console.log("Usuario desconectado");
  });
});

const sendMsg = (io, event, mensaje) => {
  // Agregar 'event' como un parámetro adicional
  io.emit(event, mensaje);
};

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Servidor escuchando en el puerto ${PORT}`);
});
