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
  const userId = 'test-user'; // 현재는 임의의 사용자 ID 사용
  console.log(`사용자 질문: ${userQuestion}`);

  if (!userQuestion) {
    return res.status(400).json({ error: "질문을 입력해주세요." });
  }

  let aiAnswer;
  let connection;

  try {
    connection = await pool.getConnection();

    // 1. 데이터베이스에서 답변 찾기
    const [faqsRows] = await connection.execute(
      "SELECT answer FROM faqs WHERE question = ?",
      [userQuestion]
    );

    if (faqsRows.length > 0) {
      // ✅ 데이터베이스에 답변이 있는 경우
      aiAnswer = faqsRows[0].answer;
    } else {
      // ✅ 데이터베이스에 답변이 없는 경우, OpenAI API 호출
      console.log("데이터베이스에 답변이 없어 OpenAI 호출");

      // 1-1. conversations 테이블에서 대화 기록 불러오기
      const [chatHistory] = await connection.execute(
          "SELECT message FROM conversations WHERE user_id = ? ORDER BY timestamp ASC",
          [userId]
      );
      
      const messages = [{
          role: "system",
          content: "You are a helpful assistant that answers questions about AWS in Korean. Your response should be friendly and easy to understand."
      }];

      // 1-2. 불러온 대화 기록을 OpenAI 메시지 형식으로 변환
      chatHistory.forEach(row => {
          // 메시지가 '질문: ...' 형식으로 저장되므로 질문과 답변을 분리
          const parts = row.message.split('\n답변: ');
          if (parts.length === 2) {
              messages.push({ role: 'user', content: parts[0].replace('질문: ', '') });
              messages.push({ role: 'assistant', content: parts[1] });
          }
      });
      // 1-3. 마지막으로 사용자의 새 질문 추가
      messages.push({ role: 'user', content: userQuestion });

      const completion = await openai.chat.completions.create({
        messages: messages, // ✅ 대화 기록을 포함한 메시지 배열 전달
        model: "gpt-3.5-turbo",
        max_tokens: 500
      });
      aiAnswer = completion.choices[0].message.content;
    }

    // ✅ 대화 기록 테이블에 질문과 답변 저장
    const timestamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
    const insertQuery = "INSERT INTO conversations (user_id, message, timestamp) VALUES (?, ?, ?)";
    await connection.execute(insertQuery, [userId, `질문: ${userQuestion}\n답변: ${aiAnswer}`, timestamp]);

    // 최종 응답 반환
    res.json({ answer: aiAnswer });

  } catch (err) {
    console.error("서버 오류:", err);
    res.status(500).json({ error: "서버 오류가 발생했습니다." });
  } finally {
    if (connection) {
      connection.release();
    }
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
