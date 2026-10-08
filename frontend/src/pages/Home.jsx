import Navbar from '../components/Navbar'
import Hero from '../components/Hero'
import FeatureCard from '../components/FeatureCard'
import Footer from '../components/Footer'

function Home() {
  return (
    <>
      <Navbar />

      <main>
        <Hero />

        <section className="features-section" id="servicos">
          <div className="section-heading">
            <span>Uma plataforma completa</span>

            <h2>
              Tudo o que você precisa em um só lugar.
            </h2>

            <p>
              Simplificamos o acesso às principais informações
              relacionadas ao seu atendimento.
            </p>
          </div>

          <div className="features-grid">
            <FeatureCard
              icon="01"
              title="Consultas"
              description="Agende, acompanhe e consulte seus atendimentos de forma rápida e organizada."
            />

            <FeatureCard
              icon="02"
              title="Exames"
              description="Acompanhe solicitações e consulte os resultados dos seus exames."
            />

            <FeatureCard
              icon="03"
              title="Atendimento"
              description="Tenha suas informações organizadas para facilitar a comunicação entre pacientes e profissionais."
            />
          </div>
        </section>

        <section className="about-section" id="sobre">
          <div className="about-content">
            <span>Atendimento conectado</span>

            <h2>
              Mais organização para profissionais.
              Mais praticidade para pacientes.
            </h2>

            <p>
              Nossa plataforma foi pensada para aproximar pacientes,
              médicos e administração, tornando os processos da clínica
              mais simples e organizados.
            </p>
          </div>

          <div className="about-highlight">
            <strong>Uma experiência</strong>
            <span>mais simples, segura e organizada.</span>
          </div>
        </section>
      </main>

      <Footer />
    </>
  )
}

export default Home