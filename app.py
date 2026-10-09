# =====================================================================
#  PAINEL DA INFLAÇÃO  🌸
#  Dados oficiais do Banco Central do Brasil (API do SGS)
#
#  Para rodar:   streamlit run app.py
# =====================================================================


# ---------------------------------------------------------------------
# PARTE 1 — IMPORTAR AS "CAIXAS DE FERRAMENTAS"
# Uma biblioteca é uma caixa de ferramentas que alguém já montou.
# Em vez de construir um martelo do zero, a gente só pega emprestado.
# ---------------------------------------------------------------------
import requests                       # o "garçom": vai até a API e traz os dados
import pandas as pd                   # a "planilha do Python": organiza os dados em tabelas
import plotly.graph_objects as go     # o "desenhista": faz gráficos bonitos e interativos
import streamlit as st                # o "construtor de sites": transforma Python em página web
from datetime import date             # ferramenta para trabalhar com datas (ex.: hoje)
import time                           # ferramenta para "esperar um pouquinho" antes de tentar de novo


# ---------------------------------------------------------------------
# PARTE 2 — CONFIGURAÇÕES DA PÁGINA E CORES
# ---------------------------------------------------------------------

# Diz ao Streamlit o título da aba do navegador, o ícone e que a página usa a tela toda.
st.set_page_config(page_title="Painel da Inflação", page_icon="🌸", layout="wide")

# Guardamos as cores em "caixinhas com nome" (variáveis) para reutilizar em todo lugar.
ROSA = "#E75A8D"          # rosa principal (destaques)
ROSA_CLARO = "#F9D5E3"    # rosa bem clarinho (fundos suaves)
CINZA = "#8A8A8F"         # cinza médio (segunda linha dos gráficos)
CINZA_CLARO = "#ECECEE"   # cinza bem claro (linhas de grade, bordas)
TEXTO = "#3A3A3A"         # cinza escuro para textos (mais suave que preto puro)

# Um pouquinho de CSS (a "roupa" do site) para deixar os cartões arredondados e limpos.
# unsafe_allow_html=True avisa: "pode usar esse estilo, eu sei o que estou fazendo".
st.markdown(
    f"""
    <style>
      /* cartões dos números principais */
      div[data-testid="stMetric"] {{
          background: #FFFFFF;
          border: 1px solid {CINZA_CLARO};
          border-left: 5px solid {ROSA};
          border-radius: 14px;
          padding: 14px 18px;
      }}
      /* título grande no topo */
      .titulo {{ font-size: 2.1rem !important; font-weight: 700; color: {TEXTO}; margin-bottom: 0; }}
      .titulo span {{ color: {ROSA}; }}
      .subtitulo {{ color: {CINZA}; margin-top: 2px; }}
      /* caixinha rosa de destaque para a resposta da pergunta */
      .resposta {{
          background: {ROSA_CLARO};
          border-radius: 14px;
          padding: 18px 22px;
          color: {TEXTO};
          font-size: 1.05rem;
      }}
      .resposta b {{ color: {ROSA}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# PARTE 3 — O CARDÁPIO: QUAIS DADOS VAMOS PEDIR AO BANCO CENTRAL
# Cada série do SGS tem um número, como um prato num cardápio.
# Escolhemos séries MENSAIS para tudo ficar na mesma "régua" (1 valor por mês).
# ---------------------------------------------------------------------
SERIES = {
    "ipca_mes": 433,     # IPCA: quanto os preços subiram no mês (%)
    "ipca_12m": 13522,   # IPCA acumulado em 12 meses (%) — a "inflação do ano"
    "selic": 4189,       # Selic do mês, em % ao ano — os juros básicos do país
    "dolar": 3698,       # Dólar (venda), média do mês, em reais
}


# ---------------------------------------------------------------------
# PARTE 4 — O GARÇOM: FUNÇÃO QUE BUSCA UMA SÉRIE NA API
# Função = uma "receita" com nome. A gente escreve uma vez e usa quantas vezes quiser.
# ---------------------------------------------------------------------

def pedir_com_paciencia(url, parametros, tentativas=5):
    """Faz o pedido à API e, se o servidor do BC tropeçar (erros 5xx), espera e tenta de novo."""
    # "Crachá" que diz ao servidor quem está pedindo. Alguns servidores tratam melhor
    # pedidos que se apresentam como um navegador comum.
    cabecalhos = {"User-Agent": "Mozilla/5.0 (painel-inflacao)", "Accept": "application/json"}

    resposta = None                                       # ainda não temos resposta nenhuma
    for tentativa in range(1, tentativas + 1):         # tentativa 1, 2, 3, 4, 5
        try:
            # requests.get faz um pedido HTTP do tipo GET ("me traz").
            # timeout=30: se a cozinha demorar mais de 30 segundos, desistimos desta vez.
            resposta = requests.get(url, params=parametros, headers=cabecalhos, timeout=30)
            # Erros 500 a 599 = "problema do lado do servidor" → vale a pena tentar de novo
            if resposta.status_code < 500:
                return resposta                           # deu certo (ou erro que não adianta repetir)
        except (requests.ConnectionError, requests.Timeout):
            pass                                          # a internet piscou → tenta de novo também

        if tentativa < tentativas:
            time.sleep(2 ** tentativa)                    # espera 2, 4, 8, 16 segundos (cada vez mais)

    # esgotou as tentativas → mostra o erro
    if resposta is None:
        raise requests.ConnectionError("Sem conexão com a API do Banco Central.")
    resposta.raise_for_status()
    return resposta


# @st.cache_data é uma "memória": se você pedir o mesmo dado de novo dentro de 6 horas,
# o Streamlit não chama o garçom outra vez — usa o que já guardou. Fica muito mais rápido.
@st.cache_data(ttl=6 * 60 * 60)
def buscar_serie(codigo, inicio, fim):
    """Pede ao Banco Central uma série entre duas datas e devolve uma tabela."""

    # Endereço da API. O {codigo} é trocado pelo número da série (ex.: 433).
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

    # O Banco Central só entrega no máximo 10 anos por pedido.
    # Então pedimos em "fatias" de 5 anos, como comer uma pizza pedaço por pedaço.
    pedacos = []                      # lista vazia onde vamos juntando as fatias
    comeco = pd.Timestamp(inicio)     # começo da primeira fatia
    final_total = pd.Timestamp(fim)   # até onde queremos chegar

    while comeco <= final_total:      # "enquanto ainda faltar pizza, continue"
        # o fim desta fatia é 5 anos depois (ou o fim total, o que vier primeiro)
        fim_fatia = min(comeco + pd.DateOffset(years=5) - pd.Timedelta(days=1), final_total)

        # Os "parâmetros" são os detalhes do pedido: formato e datas (no padrão dd/mm/aaaa).
        parametros = {
            "formato": "json",
            "dataInicial": comeco.strftime("%d/%m/%Y"),
            "dataFinal": fim_fatia.strftime("%d/%m/%Y"),
        }

        # Aqui o garçom vai até a cozinha! (com paciência: tenta de novo se a cozinha tropeçar)
        resposta = pedir_com_paciencia(url, parametros)

        # 404 = "não tenho nada nesse período" → só pulamos esta fatia.
        if resposta.status_code != 404:
            resposta.raise_for_status()      # se deu outro erro (500, 406...), avisa
            pedacos.extend(resposta.json())  # transforma o JSON em lista e junta às outras

        comeco = fim_fatia + pd.Timedelta(days=1)  # a próxima fatia começa no dia seguinte

    # Se não veio nada, devolvemos uma tabela vazia (com as colunas certas).
    if not pedacos:
        return pd.DataFrame(columns=["data", "valor"])

    # A API manda algo assim: [{"data": "01/01/2024", "valor": "0.42"}, ...]
    tabela = pd.DataFrame(pedacos)                                         # vira tabela
    tabela["data"] = pd.to_datetime(tabela["data"], format="%d/%m/%Y")    # texto → data de verdade
    tabela["valor"] = pd.to_numeric(tabela["valor"], errors="coerce")     # texto → número
    return tabela.drop_duplicates("data").sort_values("data")             # tira repetidos e ordena


def montar_tabela(inicio, fim):
    """Busca TODAS as séries do cardápio e junta numa tabela só, com uma coluna para cada."""
    colunas = {}                                       # dicionário: nome → série de valores
    for nome, codigo in SERIES.items():                # para cada prato do cardápio...
        serie = buscar_serie(codigo, inicio, fim)      # ...o garçom busca...
        colunas[nome] = serie.set_index("data")["valor"]  # ...e guardamos usando a data como "etiqueta"
    tabela = pd.DataFrame(colunas)                     # junta tudo lado a lado, alinhado pela data
    return tabela.dropna(how="all")                    # remove meses totalmente vazios


# ---------------------------------------------------------------------
# PARTE 5 — O DETETIVE: QUANTO TEMPO A SELIC DEMORA PARA SEGURAR A INFLAÇÃO?
#
# Ideia simples:
#   1) Para cada mês, vemos quanto a Selic SUBIU nos últimos 12 meses.
#   2) Olhamos o que aconteceu com a inflação 1 mês depois, 2 meses depois... até 24.
#   3) Medimos a "correlação" (de -1 a +1) entre as duas coisas:
#        perto de -1 → quando a Selic sobe, a inflação cai depois daquele tempo;
#        perto de +1 → as duas sobem juntas;
#        perto de  0 → não tem relação clara.
#   4) O número de meses com a correlação MAIS NEGATIVA é o nosso palpite.
# ---------------------------------------------------------------------
def calcular_defasagem(tabela, max_meses=24):
    subida_selic = tabela["selic"] - tabela["selic"].shift(12)  # Selic hoje – Selic 12 meses atrás

    resultados = []                                  # lista para guardar cada teste
    for meses in range(1, max_meses + 1):            # testa 1, 2, 3, ... 24 meses
        # mudança da inflação entre hoje e daqui "meses" meses
        # (.shift(-meses) "puxa" o futuro para a linha de hoje)
        mudanca_inflacao = tabela["ipca_12m"].shift(-meses) - tabela["ipca_12m"]
        correlacao = subida_selic.corr(mudanca_inflacao)          # o número de -1 a +1
        resultados.append({"meses": meses, "correlacao": correlacao})

    return pd.DataFrame(resultados)                  # tabela: meses | correlação


# ---------------------------------------------------------------------
# PARTE 6 — O ESTILISTA DOS GRÁFICOS
# Uma função que veste todos os gráficos com a mesma roupa (rosa, branco e cinza).
# ---------------------------------------------------------------------
def estilizar(fig, titulo, altura=340):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=16, color=TEXTO)),   # título do gráfico
        height=altura,                                               # altura em pixels
        plot_bgcolor="white", paper_bgcolor="white",                 # fundos brancos
        font=dict(color=TEXTO),                                      # cor das letras
        margin=dict(l=10, r=10, t=50, b=10),                         # margens pequenas
        hovermode="x unified",                     # ao passar o mouse, mostra tudo daquela data
        legend=dict(orientation="h", y=1.12, x=0),                  # legenda deitada, no topo
    )
    fig.update_xaxes(showgrid=False, linecolor=CINZA_CLARO)          # eixo X sem grade
    fig.update_yaxes(gridcolor=CINZA_CLARO, zeroline=False)          # grade cinza clarinha
    return fig


def grafico_linha(tabela, coluna, titulo, cor, sufixo):
    """Gráfico de uma linha só (ex.: dólar ao longo do tempo)."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tabela.index, y=tabela[coluna],      # X = datas, Y = valores
        mode="lines", line=dict(color=cor, width=2.5),
        name=titulo, hovertemplate=f"%{{y:.2f}}{sufixo}<extra></extra>",
    ))
    return estilizar(fig, titulo)


# ---------------------------------------------------------------------
# PARTE 7 — MONTANDO A PÁGINA (o que a pessoa vê)
# ---------------------------------------------------------------------

# Cabeçalho
st.markdown('<p class="titulo">Painel da <span>Inflação</span> 🌸</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitulo">IPCA, Selic e dólar direto da API do Banco Central (SGS)</p>',
            unsafe_allow_html=True)

# Barra lateral (sidebar): os "botões de controle" do painel
with st.sidebar:
    st.header("⚙️ Filtros")
    ano_atual = date.today().year
    # slider de dois lados: a pessoa escolhe o ano inicial e o final
    ano_inicio, ano_fim = st.slider("Período", 2000, ano_atual, (2005, ano_atual))
    st.caption("Dica: períodos longos mostram mais ciclos de alta da Selic, "
               "o que deixa a análise mais confiável.")

# Pedimos os dados. try/except = "tenta; se der errado, mostra um aviso gentil em vez de quebrar".
try:
    with st.spinner("Chamando o garçom do Banco Central... 🍽️"):
        dados = montar_tabela(date(ano_inicio, 1, 1), min(date(ano_fim, 12, 31), date.today()))
except requests.RequestException as erro:
    st.error(f"Não consegui falar com a API do Banco Central agora. Tente de novo daqui a pouco.\n\n{erro}")
    st.stop()   # para a página aqui

if dados.empty:
    st.warning("Nenhum dado encontrado para esse período.")
    st.stop()


# ----- Cartões com os números mais recentes -----
def cartao(coluna_streamlit, rotulo, serie, sufixo, inverter=False):
    """Mostra o último valor e quanto mudou em relação ao valor anterior."""
    serie = serie.dropna()                       # ignora meses sem valor
    atual, anterior = serie.iloc[-1], serie.iloc[-2]  # último e penúltimo valores
    coluna_streamlit.metric(
        label=f"{rotulo} · {serie.index[-1]:%m/%Y}",
        value=f"{atual:.2f}{sufixo}",
        delta=f"{atual - anterior:+.2f}{sufixo}",
        # "inverse": subir fica vermelho (bom para inflação, onde subir é ruim)
        delta_color="inverse" if inverter else "normal",
    )

c1, c2, c3, c4 = st.columns(4)   # 4 colunas lado a lado
cartao(c1, "IPCA 12 meses", dados["ipca_12m"], "%", inverter=True)
cartao(c2, "IPCA do mês", dados["ipca_mes"], "%", inverter=True)
cartao(c3, "Selic", dados["selic"], "% a.a.")
cartao(c4, "Dólar", dados["dolar"], "", inverter=True)

st.write("")   # um respiro (linha em branco)


# ----- Abas: cada assunto na sua gaveta -----
aba_visao, aba_pergunta, aba_dados, aba_sobre = st.tabs(
    ["📈 Visão geral", "🔍 Selic × Inflação", "📋 Dados", "ℹ️ Sobre"]
)

# ===== ABA 1: VISÃO GERAL =====
with aba_visao:
    # Gráfico grande: Selic e inflação juntas
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dados.index, y=dados["selic"], name="Selic (% a.a.)",
                             line=dict(color=CINZA, width=2.5)))
    fig.add_trace(go.Scatter(x=dados.index, y=dados["ipca_12m"], name="IPCA 12 meses (%)",
                             line=dict(color=ROSA, width=3),
                             fill="tozeroy", fillcolor="rgba(231, 90, 141, 0.08)"))
    st.plotly_chart(estilizar(fig, "Juros × Inflação", altura=420), width="stretch")

    # Dois gráficos menores lado a lado
    esquerda, direita = st.columns(2)
    with esquerda:
        fig = go.Figure(go.Bar(x=dados.index, y=dados["ipca_mes"],
                               marker_color=[ROSA if v >= 0 else CINZA for v in dados["ipca_mes"].fillna(0)],
                               hovertemplate="%{y:.2f}%<extra></extra>"))
        st.plotly_chart(estilizar(fig, "IPCA mês a mês (%)"), width="stretch")
    with direita:
        st.plotly_chart(grafico_linha(dados, "dolar", "Dólar (R$)", CINZA, ""), width="stretch")


# ===== ABA 2: A PERGUNTA =====
with aba_pergunta:
    st.subheader("Quando a Selic sobe, a inflação cai depois de quanto tempo?")

    defasagem = calcular_defasagem(dados).dropna()

    if len(dados) < 48 or defasagem.empty:
        st.info("Escolha um período de pelo menos 4 anos para a análise funcionar bem.")
    else:
        # A linha com a correlação mais negativa = melhor palpite
        melhor = defasagem.loc[defasagem["correlacao"].idxmin()]
        meses_resposta = int(melhor["meses"])

        st.markdown(
            f'<div class="resposta">Nos dados de {ano_inicio} a {ano_fim}, o efeito mais forte '
            f'aparece cerca de <b>{meses_resposta} meses</b> depois da alta da Selic '
            f'(correlação de <b>{melhor["correlacao"]:.2f}</b>).</div>',
            unsafe_allow_html=True,
        )
        st.write("")

        esquerda, direita = st.columns([1, 1])

        # Gráfico de barras: uma barra por número de meses testado
        with esquerda:
            cores = [ROSA if m == meses_resposta else CINZA_CLARO for m in defasagem["meses"]]
            fig = go.Figure(go.Bar(x=defasagem["meses"], y=defasagem["correlacao"],
                                   marker_color=cores,
                                   hovertemplate="%{x} meses: %{y:.2f}<extra></extra>"))
            fig.update_xaxes(title="meses depois da alta da Selic", dtick=3)
            fig.update_yaxes(title="correlação", range=[-1, 1])
            st.plotly_chart(estilizar(fig, "Correlação para cada atraso", altura=380), width="stretch")

        # Gráfico interativo: a pessoa "arrasta" a inflação no tempo para ver o encaixe
        with direita:
            atraso = st.slider("Puxe a inflação para trás (meses)", 0, 24, meses_resposta)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=dados.index, y=dados["selic"] - dados["selic"].shift(12),
                                     name="Variação da Selic em 12m (p.p.)",
                                     line=dict(color=CINZA, width=2)))
            fig.add_trace(go.Scatter(x=dados.index,
                                     y=(dados["ipca_12m"].shift(-atraso) - dados["ipca_12m"]),
                                     name=f"Mudança da inflação nos {atraso} meses seguintes (p.p.)",
                                     line=dict(color=ROSA, width=2.5)))
            st.plotly_chart(estilizar(fig, "Linhas em sentidos opostos = efeito da Selic", altura=330),
                            width="stretch")

        st.caption("⚠️ Correlação não é prova de causa: câmbio, preços de alimentos e energia também "
                   "mexem na inflação. O Banco Central fala em defasagens longas e variáveis — "
                   "este painel mostra o padrão médio no período escolhido.")


# ===== ABA 3: DADOS =====
with aba_dados:
    tabela_bonita = dados.rename(columns={
        "ipca_mes": "IPCA mês (%)", "ipca_12m": "IPCA 12m (%)",
        "selic": "Selic (% a.a.)", "dolar": "Dólar (R$)",
    }).sort_index(ascending=False)                       # mais recente em cima
    tabela_bonita.index = tabela_bonita.index.strftime("%m/%Y")
    st.dataframe(tabela_bonita.round(2), width="stretch", height=420)

    # Botão para baixar a tabela em CSV (abre no Excel)
    st.download_button("⬇️ Baixar CSV", tabela_bonita.to_csv(sep=";", decimal=",").encode("utf-8-sig"),
                       file_name="painel_inflacao.csv", mime="text/csv")


# ===== ABA 4: SOBRE =====
with aba_sobre:
    st.markdown(
        """
        **De onde vêm os dados?** Da API gratuita do SGS (Sistema Gerenciador de Séries Temporais)
        do Banco Central. Nenhuma senha ou cadastro é necessário.

        | Série | Código SGS |
        |---|---|
        | IPCA – variação mensal | 433 |
        | IPCA – acumulado 12 meses | 13522 |
        | Selic acumulada no mês, anualizada | 4189 |
        | Dólar (venda), média mensal | 3698 |

        Os dados ficam guardados por 6 horas para o painel abrir mais rápido.
        """
    )