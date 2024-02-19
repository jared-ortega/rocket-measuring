const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;
const path = require('path'); // Agrega esta línea

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Running on ${PORT}`);
});
