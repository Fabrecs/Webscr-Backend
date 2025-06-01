exports = async function (changeEvent) {
  const doc = changeEvent.fullDocument;

  if (!doc.caption || doc.caption_embedding) {
    return;
  }

  const db = context.services.get("Cluster0").db("fabrecsai");
  const wardrobe = db.collection("wardrobe");

  try {
    const hf_key = context.values.get("huggingface_value");

    if (!hf_key) {
      console.error("Hugging Face key not found in context values.");
      return;
    }
    const response = await context.http.post({
      url: "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
      headers: {
        "Content-Type": ["application/json"],
        Authorization: [`Bearer ${hf_key}`], // your Hugging Face token
      },
      body: JSON.stringify({
        inputs: doc.caption,
      }),
    });
    console.log(response.statusCode);
    const result = EJSON.parse(response.body.text());

    // The result will now be a pure embedding array like: [0.1, 0.2, 0.3, ...]
    console.log("Embeddings:", result);

    const embedding = result;
    console.log("Hugging Face Response:", EJSON.stringify(result));
    console.log("Raw Response Body:", EJSON.stringify(response.body));

    if (!embedding) {
      console.log(EJSON.parse(response.text()));
      console.error("Failed to generate embedding from Hugging Face.");
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));

    const updateResult = await wardrobe.updateOne(
      { _id: doc._id },
      { $set: { caption_embedding: embedding } }
    );

    console.log("Update Result:", EJSON.stringify(updateResult));
    const wardrobeCount = await wardrobe.count();
    console.log("Wardrobe collection total docs:", wardrobeCount);
  } catch (err) {
    console.error("Error generating embedding:", err);
  }
};
