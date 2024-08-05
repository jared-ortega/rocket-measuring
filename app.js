require("dotenv").config();
const express = require("express");
const fs = require("fs");
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
let recordData = false;
let sendData = true;
let liftoff = false;

let dataArray = [];

//Este objeto guardara los resultados del test (tambien en un csv dentro del servidor)
let telemetryResult = {
    timestamps: [],
    measurements: [],
};

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

app.get("/json-files", (req, res) => {
    const directoryPath = path.join(__dirname, "measures");

    fs.readdir(directoryPath, (err, files) => {
        if (err) {
            return res.status(500).send("Unable to scan directory: " + err);
        }

        const jsonFiles = files.filter(
            (file) => path.extname(file) === ".json"
        );
        const jsonData = [];

        jsonFiles.forEach((file, index) => {
            const filePath = path.join(directoryPath, file);
            const data = fs.readFileSync(filePath, "utf8");
            jsonData.push(JSON.parse(data));
        });

        res.json(jsonData);
    });
});

//update telemtry
const updateTele = (measurement) => {
    //tomo objeto y lo actualizo
    const time = Date.now().toString();

    telemetry.timestamps.push(time);
    telemetry.measurements.push(measurement);
    console.log("Telemetry obj:", telemetry);

    //si esta recordData = true y el array
    //telemetry.timestamps.lenght = 3000 entonces
    //guardo el array en un json y set recordData = false
    if (
        recordData === true &&
        telemetry.measurements.length >= process.env.DATA_SAMPLES
    ) {
        console.log("entra en save data");
        recordData = false;
        const dataFile = JSON.stringify(telemetry);

        const filePath = path.join(
            __dirname,
            "/measures",
            `file-data-${time}.json`
        );
        fs.writeFileSync(filePath, dataFile);

        clearTele();
    }
};

const clearTele = () => {
    telemetry.timestamps = [];
    telemetry.measurements = [];
};

const setTare = () => {
    let lastValue = telemetry.measurements[telemetry.measurements.length - 1];
    calibrationValue = lastValue;
};

//start func
const initTest = () => {
    setTare();
    clearTele();
    recordData = true;
    liftoff = true;
};

//Change sendData
const setSendData = () => {
    if (sendData) {
        sendData = false;
    } else {
        sendData = true;
    }
};

//new amazing serial connection
const { DelimiterParser } = require("@serialport/parser-delimiter");
const port = new SerialPort({
    path: process.env.SERIAL_PORT,
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
    //console.log("value: ", valueN);

    //updateTelemetry array
    updateTele(valueN.toString());

    //send data
    if (sendData) {
        sendMsg(io, "rtweight", valueN);
    }

    if (liftoff) {
        port.write("1", (err) => {
            if (err) {
                return console.log("Error liftoff");
            }
            console.log("liftoff success!");
        });
    }
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
    socket.on("serverInput", (msg) => {
        switch (msg) {
            case "tare":
                console.log("Entra el funcion tara");
                setTare();
                break;
            case "start":
                console.log("Entra en la funcion start");
                initTest();
                break;
            case "clear":
                console.log("Entra en la funcion clear");
                clearTele();
                break;
            case "save":
                console.log("Entra en la funcion save");
                break;
            case "sendData":
                console.log("Entra en la funcion setSendData");
                setSendData();
                break;
            default:
                console.log("Entra en default");
        }
    });

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
