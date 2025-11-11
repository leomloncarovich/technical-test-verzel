import type { SVGProps } from 'react';

export default function HeroConsultoria() {
  return (
    <section 
      className="relative w-full overflow-hidden bg-gradient-to-br from-gray-50 via-white to-gray-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900"
      aria-labelledby="hero-title"
    >
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 md:py-10">
        <div className="rounded-xl sm:rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 shadow-xl sm:p-5 md:p-6 text-center">
          <header className="mb-3 sm:mb-4">
            <h1 
              id="hero-title"
              className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl"
            >
              <span className="bg-gradient-to-r from-sky-600 to-cyan-600 dark:from-sky-300 dark:to-cyan-200 bg-clip-text text-transparent">
                Consultoria em problemas de logística
              </span>
            </h1>
          </header>

          <p className="mb-4 text-sm leading-relaxed text-gray-700 dark:text-slate-200/90 sm:text-base md:text-base mx-auto max-w-2xl">
            Identificamos o seu gargalo operacional (rotas, estoque, regiões críticas, controle de entrada/saída)
            e marcamos uma reunião onde <strong className="text-sky-600 dark:text-sky-300">especialistas em logística</strong> irão participar para apresentar uma solução personalizada.
          </p>

          <ul 
            className="mb-4 grid gap-1.5 text-xs text-gray-600 dark:text-slate-200/80 sm:text-sm md:text-sm mx-auto max-w-xl"
            role="list"
            aria-label="Benefícios do serviço"
          >
            <li className="flex items-start justify-center gap-2">
              <CheckIcon 
                className="mt-0.5 h-4 w-4 flex-none text-sky-600 dark:text-sky-300 sm:h-5 sm:w-5" 
                aria-hidden="true"
              />
              <span className="text-left">Focado em empresas de logística (transportadoras, centros de distribuição, armazéns)</span>
            </li>
            <li className="flex items-start justify-center gap-2">
              <CheckIcon 
                className="mt-0.5 h-4 w-4 flex-none text-sky-600 dark:text-sky-300 sm:h-5 sm:w-5" 
                aria-hidden="true"
              />
              <span className="text-left">Diagnóstico rápido via chat</span>
            </li>
            <li className="flex items-start justify-center gap-2">
              <CheckIcon 
                className="mt-0.5 h-4 w-4 flex-none text-sky-600 dark:text-sky-300 sm:h-5 sm:w-5" 
                aria-hidden="true"
              />
              <span className="text-left">Agendamento automático da reunião com especialistas</span>
            </li>
          </ul>

          <p className="text-xs text-gray-600 dark:text-slate-300/70 sm:text-sm md:text-sm mx-auto max-w-xl">
            <strong className="text-sky-600 dark:text-sky-300">Comece agora:</strong> Digite sua mensagem no chat abaixo para iniciar o diagnóstico.
          </p>
        </div>
      </div>
    </section>
  );
}

function CheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg 
      viewBox="0 0 24 24" 
      fill="none" 
      aria-hidden="true" 
      {...props}
    >
      <path
        d="M20 7L10 17l-6-6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
