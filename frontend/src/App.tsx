import Chat from './components/Chat';
import HeroConsultoria from './components/HeroConsultoria';

export default function App() {
  return (
    <main className="min-h-screen w-full bg-gray-50 dark:bg-gray-900 font-sans">
      <HeroConsultoria />
      <div className="w-full max-w-5xl mx-auto px-4 py-6 sm:px-6 sm:py-8">
        <Chat />
      </div>
    </main>
  );
}
