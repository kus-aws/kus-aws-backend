import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
import json


# Ensure project root is on PYTHONPATH for `import app`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def mock_bedrock():
    """Bedrock 호출을 모킹하여 테스트 환경에서 AWS 자격 증명 없이도 테스트할 수 있도록 합니다."""
    with patch('app.main.invoke_bedrock') as mock:
        # 채팅 응답 모킹
        def mock_invoke_bedrock(prompt, max_tokens=1000):
            if "연쇄법칙" in prompt or "테스트 질문" in prompt:
                return "연쇄법칙은 미분에서 합성함수의 도함수를 구하는 방법입니다. f(g(x))의 도함수는 f'(g(x)) * g'(x)입니다."
            elif "제안" in prompt:
                return "미분의 기하학적 의미는?\n적분과의 관계는?\n실생활 응용 예시는?"
            else:
                return "AI 응답입니다."
        
        mock.side_effect = mock_invoke_bedrock
        yield mock


