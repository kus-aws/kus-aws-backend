const express = require('express');
const mysql = require('mysql2/promise');
const dotenv = require('dotenv');
const cors = require('cors');
const OpenAI = require("openai");

dotenv.config();
const app = express();
app.use(cors());
app.use(express.json());

const pool = mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_DATABASE,
  port: process.env.DB_PORT || 3306
});

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY }); 

const initDatabase = async () => {
  try {
    const connection = await pool.getConnection();
    console.log("데이터베이스 연결 완료");

    const createConversationsTable = `
      CREATE TABLE IF NOT EXISTS conversations (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        KEY idx_user_id_timestamp (user_id, timestamp)
      ) ENGINE=InnoDB;
    `;
    await connection.execute(createConversationsTable);
    console.log("Conversations 테이블 생성 완료");

    const createFaqsTable = `
      CREATE TABLE IF NOT EXISTS faqs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        subfield VARCHAR(255) NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        KEY idx_subfield_question (subfield, question(255))
      ) ENGINE=InnoDB;
    `;
    await connection.execute(createFaqsTable);
    console.log("FAQs 테이블 생성 완료");

    connection.release();
  } catch (err) {
    console.error("데이터베이스 초기화 중 오류 발생:", err);
    process.exit(1);
  }
};

app.get("/api/v1/ask", async (req, res) => {
  const userQuestion = req.query.q;
  console.log(`사용자 질문: ${userQuestion}`);

  if (!userQuestion) {
    return res.status(400).json({ error: "질문을 입력해주세요." });
  }

  try {
    // 1. 데이터베이스에서 답변 찾기
    const [rows] = await pool.execute(
      "SELECT answer FROM faqs WHERE question = ?",
      [userQuestion]
    );

    if (rows.length > 0) {
      return res.json({ answer: rows[0].answer });
    } else {
      console.log("데이터베이스에 답변이 없어 OpenAI 호출");
      const completion = await openai.chat.completions.create({
        messages: [
          {
            role: "system",
            content: "You are a helpful assistant that answers questions about AWS in Korean. Your response should be friendly and easy to understand."
          },
          {
            role: "user",
            content: userQuestion
          }
        ],
        model: "gpt-3.5-turbo",
        max_tokens: 500
      });
      const aiAnswer = completion.choices[0].message.content;

      return res.json({ answer: aiAnswer });
    }
  } catch (err) {
    console.error("서버 오류:", err);
    res.status(500).json({ error: "서버 오류가 발생했습니다." });
  }
});

app.get("/", (req, res) => {
  res.json({ message: "서버 연결 완료" });
});

app.get("/api/v1/echo", (req, res) => {
  res.json({ echo: req.query.q || "hello" });
});

const port = 8000;
app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
  initDatabase();
});
