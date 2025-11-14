<div align="center">
  <svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#2dd4bf" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M16 16.5a2.5 2.5 0 0 0-5 0"></path>
    <path d="M12 14v7"></path>
    <path d="M4 16.5a2.5 2.5 0 0 0 5 0"></path>
    <path d="M12 2v7"></path>
    <path d="M7 7l-5 5"></path>
    <path d="m17 7 5 5"></path>
    <path d="M2 12h20"></path>
  </svg>
  
  <h1 style="border-bottom: none; font-size: 36px;">
    Tradu<span style="color: #2dd4bf;">Pay</span>
  </h1>
  
  <p style="font-size: 1.2rem;">Inteligência Contábil para decisões de carreira.</p>

  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&style=for-the-badge" alt="Python Badge">
  <img src="https://img.shields.io/badge/Django-4.2%2B-darkgreen?logo=django&style=for-the-badge" alt="Django Badge">
</div>

## 🎯 O Projeto

**TraduPay** é um comparador salarial focado na **transparência total**. Ele abandona a comparação enganosa de "Bruto vs. Bruto" e traduz propostas CLT e PJ para o único valor que realmente importa: o **dinheiro líquido** no bolso do profissional.

### 🌍 Contexto: FIAP Global Solution

Este projeto foi desenvolvido para a **Global Solution da FIAP**, um desafio focado em criar soluções tecnológicas que apoiem os **Objetivos de Desenvolvimento Sustentável (ODS) da ONU**. O TraduPay contribui para:

* **ODS 8 (Trabalho Decente):** Promovendo relações de trabalho justas e transparentes.
* **ODS 4 (Educação de Qualidade):** Atuando como uma ferramenta de educação financeira e fiscal.

## ✨ Diferenciais Técnicos

O diferencial do TraduPay é sua **precisão contábil**:

1.  **Cálculo CLT Realista:** Desconta automaticamente as tabelas progressivas de **INSS** e **IRRF (Imposto de Renda)** para chegar ao salário líquido.
2.  **Otimização PJ (Fator R):** Simula automaticamente o Anexo III vs. Anexo V e escolhe o cenário tributário mais vantajoso (que paga menos imposto).
3.  **Comparação "Líquido vs. Líquido":** A única comparação justa, mostrando o valor real de cada proposta.

## 🚀 Como Executar

1.  **Clone o repositório:**
    ```bash
    git clone https://[seu-repositorio]/tradupay.git && cd tradupay
    ```
2.  **Instale as dependências:**
    ```bash
    pip install django pandas
    ```
3.  **Inicie o servidor:**
    (Certifique-se que `salarios_mercado.csv` está em `core/`)
    ```bash
    python manage.py runserver
    ```
4.  Acesse `http://127.0.0.1:8000/`.
