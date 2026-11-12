import React, { useState } from 'react';
import { loginLocaweb } from '../services/api';

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const emailTrim = email.trim().toLowerCase();
    if (!emailTrim.endsWith('@inteligentte.com.br')) {
      setErrorMsg('Apenas e-mails corporativos @inteligentte.com.br têm acesso a este ecossistema.');
      return;
    }

    if (!senha) {
      setErrorMsg('Por favor, informe a sua senha do Webmail.');
      return;
    }

    setIsLoading(true);
    try {
      await loginLocaweb(emailTrim, senha);
      onLoginSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || 'Credenciais inválidas. Verifique seu e-mail e senha corporativa.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: '24px',
      position: 'relative',
      zIndex: 10
    }}>
      <div style={{
        width: '100%',
        maxWidth: '460px',
        backgroundColor: '#0E0E14',
        border: '1.5px solid #1F1F2C',
        borderRadius: '8px',
        padding: '40px 32px',
        boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
        backdropFilter: 'blur(16px)'
      }}>
        {/* Header da Marca */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono, monospace)',
            fontWeight: 800,
            letterSpacing: '0.15em',
            color: 'var(--blue-prime, #0052FF)',
            textTransform: 'uppercase',
            marginBottom: '8px'
          }}>
            INTELIGENTTE // AUTONOMOUS REVENUE
          </div>
          <h1 style={{
            fontSize: '24px',
            fontWeight: 900,
            color: '#FFFFFF',
            margin: '0 0 8px 0',
            fontFamily: 'var(--font-title, sans-serif)',
            letterSpacing: '-0.02em'
          }}>
            Acesso Corporativo
          </h1>
          <p style={{
            fontSize: '14px',
            color: 'var(--text-muted, #94A3B8)',
            margin: 0,
            lineHeight: 1.5
          }}>
            Autentique-se com sua conta de e-mail corporativo da Locaweb (@inteligentte.com.br)
          </p>
        </div>

        {/* Mensagem de Erro */}
        {errorMsg && (
          <div style={{
            backgroundColor: 'rgba(255, 30, 70, 0.1)',
            border: '1px solid rgba(255, 30, 70, 0.4)',
            borderRadius: '6px',
            padding: '12px 16px',
            marginBottom: '24px',
            color: '#FF6B8B',
            fontSize: '13px',
            lineHeight: 1.4,
            fontWeight: 600
          }}>
            {errorMsg}
          </div>
        )}

        {/* Formulário */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: '12px',
              fontFamily: 'var(--font-mono, monospace)',
              fontWeight: 700,
              textTransform: 'uppercase',
              color: 'var(--text-muted, #94A3B8)',
              marginBottom: '8px'
            }}>
              E-mail Corporativo
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ex: equipe@inteligentte.com.br"
              disabled={isLoading}
              required
              style={{
                width: '100%',
                boxSizing: 'border-box',
                backgroundColor: '#08080A',
                border: '1.5px solid #272738',
                borderRadius: '6px',
                padding: '12px 14px',
                color: '#FFFFFF',
                fontSize: '14px',
                fontFamily: 'inherit',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
              onFocus={(e) => (e.target.style.borderColor = 'var(--blue-prime, #0052FF)')}
              onBlur={(e) => (e.target.style.borderColor = '#272738')}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: '12px',
              fontFamily: 'var(--font-mono, monospace)',
              fontWeight: 700,
              textTransform: 'uppercase',
              color: 'var(--text-muted, #94A3B8)',
              marginBottom: '8px'
            }}>
              Senha do Webmail Locaweb
            </label>
            <input
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="Sua senha corporativa"
              disabled={isLoading}
              required
              style={{
                width: '100%',
                boxSizing: 'border-box',
                backgroundColor: '#08080A',
                border: '1.5px solid #272738',
                borderRadius: '6px',
                padding: '12px 14px',
                color: '#FFFFFF',
                fontSize: '14px',
                fontFamily: 'inherit',
                outline: 'none',
                transition: 'border-color 0.2s'
              }}
              onFocus={(e) => (e.target.style.borderColor = 'var(--blue-prime, #0052FF)')}
              onBlur={(e) => (e.target.style.borderColor = '#272738')}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            style={{
              marginTop: '10px',
              padding: '14px',
              backgroundColor: isLoading ? '#1A365D' : 'var(--blue-prime, #0052FF)',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 800,
              fontSize: '14px',
              fontFamily: 'var(--font-title, sans-serif)',
              letterSpacing: '0.02em',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}
          >
            {isLoading ? 'Autenticando na Locaweb...' : 'Entrar no Ecossistema'}
          </button>
        </form>

        {/* Rodapé Seguro */}
        <div style={{
          marginTop: '32px',
          paddingTop: '20px',
          borderTop: '1px solid #1F1F2C',
          textAlign: 'center',
          fontSize: '12px',
          color: '#64748B'
        }}>
          Autenticação criptografada via IMAP SSL (993) na infraestrutura oficial Locaweb.
        </div>
      </div>
    </div>
  );
};
