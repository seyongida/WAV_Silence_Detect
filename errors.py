# 오디오 분석기 오류 코드 및 예외 클래스 정의

# 오류 코드 상수
ERR_FILE_NOT_FOUND = "ERR_FILE_NOT_FOUND"
ERR_INVALID_FORMAT = "ERR_INVALID_FORMAT"
ERR_TOO_SHORT = "ERR_TOO_SHORT"
ERR_DELAY_FAILED = "ERR_DELAY_FAILED"


class AudioAnalyzerError(Exception):
    """오디오 분석기 기본 예외 클래스.

    매개변수:
        code (str): 오류 코드 상수 (ERR_* 형태)
        message (str): 사람이 읽을 수 있는 오류 설명
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
