const { createWorker } = require('tesseract.js');
const fs = require('fs');
const path = require('path');

const slidesDir = path.join(__dirname, 'gambar_input');

async function run() {
  const files = fs.readdirSync(slidesDir).filter(f => f.endsWith('.png')).sort();
  if (files.length === 0) {
    console.log("No PNG files found in gambar_input/");
    return;
  }
  
  console.log("Initializing Tesseract worker...");
  const worker = await createWorker('ind'); // Load Indonesian language pack
  
  for (const file of files) {
    console.log(`\n======================================`);
    console.log(`FILE: ${file}`);
    console.log(`======================================`);
    const filePath = path.join(slidesDir, file);
    try {
      const { data: { text } } = await worker.recognize(filePath);
      console.log(text);
    } catch (err) {
      console.error(`Error processing ${file}:`, err.message);
    }
  }
  
  await worker.terminate();
  console.log("\nOCR processing completed!");
}

run().catch(console.error);
