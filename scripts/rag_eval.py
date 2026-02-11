import asyncio
from pathlib import Path

from drive_service import DriveService
from knowledge_base import KnowledgeBase

QUERIES_FILE = Path(__file__).with_name('rag_eval_queries.txt')


def load_queries():
    if not QUERIES_FILE.exists():
        return []
    lines = []
    for line in QUERIES_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # strip numeric prefix like "1)"
        if ')' in line[:4]:
            line = line.split(')', 1)[1].strip()
        lines.append(line)
    return lines


async def main():
    queries = load_queries()
    if not queries:
        print('No queries found. Fill scripts/rag_eval_queries.txt')
        return

    drive = DriveService()
    kb = KnowledgeBase(drive)

    # Refresh KB to ensure latest local index
    await kb.refresh_cache()

    print('=== RAG Quick Eval ===')
    for i, q in enumerate(queries, 1):
        ctx = kb.get_relevant_context(q, top_k=3)
        sources = []
        for line in ctx.splitlines():
            if line.startswith('--- Fragment') and 'Source:' in line:
                # Extract source name
                start = line.find('Source:')
                src = line[start + len('Source:'):].strip(' -')
                sources.append(src)
        src_preview = ', '.join(sources[:3]) if sources else 'no matches'
        print(f"{i:02d}. {q}\n    -> {src_preview}")


if __name__ == '__main__':
    asyncio.run(main())
