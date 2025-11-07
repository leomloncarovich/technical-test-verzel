import Chat from './components/Chat'

export default function App(){
  return (
    <main>
      <h1>SDR Agent</h1>
      <Chat />
      <style>{`
        main { font-family: system-ui, -apple-system, Segoe UI, Roboto; padding: 16px; }
        h1 { text-align: center; }
      `}</style>
    </main>
  )
}
