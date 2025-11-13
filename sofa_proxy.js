// ===== sofa_proxy.js =====
const express = require("express");
const cors = require("cors");
const fetch = (...args) =>
  import("node-fetch").then(({ default: fetch }) => fetch(...args));

const app = express();
app.use(cors());

const SOFA_URL = "https://sofascore.p.rapidapi.com/sport/tennis/events/live";

app.get("/live", async (req, res) => {
  try {
    const response = await fetch(SOFA_URL, {
      headers: {
        "X-RapidAPI-Key": "491de2f94emsh815cefbc25b4a41p12296ejsn679d321c7031",
        "X-RapidAPI-Host": "sofascore.p.rapidapi.com",
      },
    });

    if (!response.ok) {
      console.log("❌ Sofascore error:", response.status);
      return res.status(response.status).json({ error: response.statusText });
    }

    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error("Proxy error:", err);
    res.status(500).json({ error: err.toString() });
  }
});

const PORT = 3000;
app.listen(PORT, () =>
  console.log(`✅ Sofascore proxy запущен на http://localhost:${PORT}/live`)
);
