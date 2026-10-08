function Hero() {
  return (
    <section className="hero-section" id="inicio">
      <div className="hero-content">
        <span className="hero-tag">Cuidado que acompanha você</span>

        <h1>
          Sua saúde mais
          <span> simples e conectada.</span>
        </h1>

        <p>
          Tenha acesso às suas consultas, exames e informações de saúde
          em um só lugar, de forma prática, segura e organizada.
        </p>

        <div className="hero-actions">
          <a href="#" className="primary-button">
            Acessar plataforma
          </a>

          <a href="#servicos" className="secondary-button">
            Conheça os serviços
          </a>
        </div>
      </div>

      <div className="hero-visual">
        <div className="hero-card main-card">
          <div className="card-header">
            <span>Próxima consulta</span>
            <span className="status">Confirmada</span>
          </div>

          <div className="doctor-info">
            <div className="doctor-avatar">DR</div>

            <div>
              <strong>Dr. Carlos Oliveira</strong>
              <span>Cardiologia</span>
            </div>
          </div>

          <div className="appointment-info">
            <div>
              <small>Data</small>
              <strong>05 Out, 2026</strong>
            </div>

            <div>
              <small>Horário</small>
              <strong>14:00</strong>
            </div>
          </div>
        </div>

        <div className="floating-card">
          <span className="floating-icon">✓</span>

          <div>
            <strong>Exame disponível</strong>
            <span>Seu resultado já está disponível</span>
          </div>
        </div>
      </div>
    </section>
  )
}

export default Hero