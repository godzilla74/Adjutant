// ui/src/components/MarkdownContent.tsx
import ReactMarkdown, { Components } from 'react-markdown'

const components: Components = {
  h1:     ({ children }) => <p className="font-bold text-zinc-200 mt-2 mb-1">{children}</p>,
  h2:     ({ children }) => <p className="font-semibold text-zinc-200 mt-2 mb-0.5">{children}</p>,
  h3:     ({ children }) => <p className="font-medium text-zinc-300 mt-1 mb-0.5">{children}</p>,
  p:      ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
  ul:     ({ children }) => <ul className="list-disc pl-4 mb-1.5 space-y-0.5">{children}</ul>,
  ol:     ({ children }) => <ol className="list-decimal pl-4 mb-1.5 space-y-0.5">{children}</ol>,
  li:     ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-zinc-200">{children}</strong>,
  em:     ({ children }) => <em className="italic text-zinc-400">{children}</em>,
  hr:     () => <hr className="border-zinc-700 my-2" />,
  table:  ({ children }) => <table className="border-collapse w-full my-1.5">{children}</table>,
  th:     ({ children }) => <th className="border border-zinc-700 px-2 py-1 text-left font-semibold text-zinc-300">{children}</th>,
  td:     ({ children }) => <td className="border border-zinc-700 px-2 py-1 text-zinc-400">{children}</td>,
  code:   ({ children }) => <code className="bg-zinc-950/60 rounded px-1 font-mono text-zinc-300">{children}</code>,
  pre:    ({ children }) => <pre className="bg-zinc-950/60 rounded p-2 overflow-x-auto my-1.5">{children}</pre>,
}

interface Props {
  children: string
  className?: string
}

export default function MarkdownContent({ children, className }: Props) {
  return (
    <div className={className}>
      <ReactMarkdown components={components}>{children}</ReactMarkdown>
    </div>
  )
}
