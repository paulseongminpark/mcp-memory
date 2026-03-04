"""Markdown → 청크 분할. ## 기준 + 오버랩."""

import re


def chunk_markdown(
    text: str,
    source_path: str = "",
    max_tokens: int = 400,
    overlap_tokens: int = 50,
) -> list[dict]:
    """마크다운 텍스트를 ## 헤더 기준으로 청크 분할.

    Returns list of {"content": str, "heading": str, "source": str, "index": int}
    """
    # ## 기준으로 섹션 분리
    sections = _split_by_headings(text)

    chunks = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        # 토큰 추정 (한글: ~1.5 char/token, 영문: ~4 char/token, 대략 2.5 평균)
        est_tokens = len(body) / 2.5
        if est_tokens <= max_tokens:
            chunks.append({
                "content": f"## {heading}\n{body}" if heading else body,
                "heading": heading,
                "source": source_path,
                "index": len(chunks),
            })
        else:
            # 긴 섹션은 문단 기준으로 재분할
            sub_chunks = _split_long_section(heading, body, max_tokens, overlap_tokens)
            for sc in sub_chunks:
                sc["source"] = source_path
                sc["index"] = len(chunks)
                chunks.append(sc)

    return chunks


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """## 또는 # 기준으로 섹션 분리. (heading, body) 튜플 리스트."""
    pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))

    if not matches:
        return [("", text)]

    sections = []
    # 첫 헤더 이전 텍스트
    if matches[0].start() > 0:
        pre = text[: matches[0].start()].strip()
        if pre:
            sections.append(("", pre))

    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append((heading, body))

    return sections


def _split_long_section(
    heading: str,
    body: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[dict]:
    """긴 섹션을 문단 기준으로 분할."""
    paragraphs = re.split(r"\n\n+", body)
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_tokens = len(para) / 2.5
        if current_len + para_tokens > max_tokens and current:
            chunk_text = "\n\n".join(current)
            if heading:
                chunk_text = f"## {heading}\n{chunk_text}"
            chunks.append({"content": chunk_text, "heading": heading})
            # 오버랩: 마지막 문단 유지
            if overlap_tokens > 0 and current:
                last = current[-1]
                current = [last]
                current_len = len(last) / 2.5
            else:
                current = []
                current_len = 0
        current.append(para)
        current_len += para_tokens

    if current:
        chunk_text = "\n\n".join(current)
        if heading:
            chunk_text = f"## {heading}\n{chunk_text}"
        chunks.append({"content": chunk_text, "heading": heading})

    return chunks
