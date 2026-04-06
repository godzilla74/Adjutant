import { useState, FormEvent } from 'react'

interface Props {
  onSubmit: (password: string) => void
  connecting: boolean
}

export default function PasswordGate({ onSubmit, connecting }: Props) {
  const [password, setPassword] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (password) onSubmit(password)
  }

  return (
    <div className="flex h-full items-center justify-center bg-zinc-950">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 w-72">
        <h1 className="text-xl font-semibold text-zinc-100 text-center">Hannah</h1>
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          disabled={connecting}
          className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-sky-600"
          autoFocus
        />
        <button
          type="submit"
          disabled={connecting || !password}
          className="rounded-xl bg-sky-600 py-3 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40 transition-colors"
        >
          {connecting ? 'Connecting…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
