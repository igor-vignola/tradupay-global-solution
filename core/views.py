# core/views.py (VERSÃO CORRIGIDA E FIDEDIGNA)

from django.shortcuts import render
import pandas as pd
import os
import json
import numpy as np 
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ===================================================================
# CARREGAR A BASE DE DADOS (Sem mudanças)
# ===================================================================
try:
    CSV_PATH = os.path.join(os.path.dirname(__file__), 'salarios_mercado.csv')
    # Adicionamos parse_dates para o Pandas ler a coluna de data corretamente
    df_market = pd.read_csv(CSV_PATH, parse_dates=['data_ref'])
    
    # Listas para os dropdowns (mantemos igual)
    AREAS_LIST = sorted(df_market['area'].unique())
    SENIORITIES_LIST = ['Júnior', 'Pleno', 'Sênior']
    LOCATIONS_LIST = sorted(df_market['location'].unique())
except FileNotFoundError:
    print("ERRO: 'salarios_mercado.csv' não encontrado.")
    df_market = pd.DataFrame()
    AREAS_LIST = []
    SENIORITIES_LIST = []
    LOCATIONS_LIST = []

# ===================================================================
# CONSTANTES E TABELAS FISCAIS (NOVAS)
# ===================================================================
MEI_MONTHLY_REVENUE_LIMIT = 6750.00
DAS_MEI_FIXED_VALUE = 72.00 
MINIMUM_WAGE = 1412.00 # Salário Mínimo 2024

# Tabela Progressiva INSS (2024)
INSS_TABLE = [
    (1412.00, 0.075),
    (2666.68, 0.09),
    (4000.03, 0.12),
    (7786.02, 0.14),
]
INSS_CEILING = 908.85  # Teto do desconto do INSS

# Tabela Progressiva IRRF (2024 - Simplificada com desconto 564.80)
# (Limite da Faixa, Alíquota, Parcela a Deduzir)
IRRF_TABLE = [
    (2259.20, 0.00, 0.00),     # Isento
    (2826.65, 0.075, 169.44),
    (3751.05, 0.15, 381.44),
    (4664.68, 0.225, 662.77),
    (float('inf'), 0.275, 896.00),
]
# Desconto simplificado opcional do IRRF (ou por deduções legais)
# Usaremos o simplificado para este cálculo, que na prática sobe a isenção
IRRF_SIMPLIFIED_DEDUCTION = 564.80
IRRF_DEPENDENT_DEDUCTION = 189.59 # (Não usado no app ainda, mas é o valor real)

# Alíquotas Simples Nacional (Anexos para Serviços de TI/MKT/Design)
# (Assumindo faturamento anual até 180k para simplificar)
ANEXO_III_RATE = 0.06  # 6% (Com Fator R)
ANEXO_V_RATE = 0.155 # 15.5% (Sem Fator R)

# ===================================================================
# FUNÇÕES DE CÁLCULO FISCAL (NOVAS)
# ===================================================================

def format_currency(value):
    try:
        val_str = f"{value:,.2f}"
        return f"R$ {val_str.replace(',', 'X').replace('.', ',').replace('X', '.')}"
    except (ValueError, TypeError):
        return "R$ 0,00"

def calculate_inss_clt(gross_salary):
    """Calcula o INSS progressivo sobre o salário CLT."""
    if gross_salary > 7786.02:
        return INSS_CEILING
    
    tax = 0
    previous_limit = 0
    for limit, rate in INSS_TABLE:
        if gross_salary > limit:
            taxable_slice = limit - previous_limit
            tax += taxable_slice * rate
            previous_limit = limit
        else:
            taxable_slice = gross_salary - previous_limit
            tax += taxable_slice * rate
            break
    return tax

def calculate_irrf(base_salary):
    """
    Calcula o IRRF sobre uma base de cálculo (Bruto - INSS).
    Usa o desconto simplificado de R$ 564,80.
    """
    # Aplicar o desconto simplificado
    taxable_base = base_salary - IRRF_SIMPLIFIED_DEDUCTION
    
    if taxable_base <= 2259.20: # Limite de isenção pós-desconto
         return 0.0

    for limit, rate, deduction in IRRF_TABLE:
        if taxable_base <= limit:
            tax = (taxable_base * rate) - deduction
            return max(0, tax) # Imposto não pode ser negativo
    return 0.0 # Fallback

# ===================================================================
# LÓGICA DE CÁLCULO (CLT ATUALIZADA)
# ===================================================================

def calculate_clt_equivalent_monthly_value(gross_salary, extra_benefits=0):
    """
    Calcula o VALOR LÍQUIDO EQUIVALENTE do CLT.
    (Bruto - Descontos) + Benefícios (Líquidos/12) + FGTS.
    """
    
    # 1. Calcular Descontos do Salário Mensal
    inss_discount = calculate_inss_clt(gross_salary)
    base_for_irrf = gross_salary - inss_discount
    irrf_discount = calculate_irrf(base_for_irrf)
    
    net_salary = gross_salary - inss_discount - irrf_discount
    
    # 2. Calcular Benefícios Mensalizados
    # FGTS é sempre sobre o bruto e não tem desconto
    fgts_monthly = gross_salary * 0.08
    
    # 13º (Líquido)
    # Nota: O cálculo real do 13º tem descontos próprios, mas usar o
    # salário líquido como base é uma aproximação 99% correta.
    net_thirteenth_monthly = net_salary / 12
    
    # Férias + 1/3 (Líquido)
    gross_vacation = gross_salary * (1 + 1/3)
    # INSS e IRRF também incidem sobre as férias
    inss_vacation = calculate_inss_clt(gross_vacation)
    irrf_vacation = calculate_irrf(gross_vacation - inss_vacation)
    net_vacation = gross_vacation - inss_vacation - irrf_vacation
    net_vacation_monthly = net_vacation / 12
    
    # 3. Valor Total Equivalente (Dinheiro no bolso + Patrimônio)
    equivalent_value = net_salary + net_thirteenth_monthly + net_vacation_monthly + fgts_monthly + extra_benefits
    
    return {
        'grossSalary': gross_salary,
        'extraBenefits': extra_benefits,
        'inssDiscount': inss_discount,           # NOVO
        'irrfDiscount': irrf_discount,           # NOVO
        'netSalary': net_salary,                 # NOVO
        'thirteenthMonthly': net_thirteenth_monthly, # Agora é líquido
        'vacationMonthly': net_vacation_monthly,     # Agora é líquido
        'fgtsMonthly': fgts_monthly,
        'equivalentValue': equivalent_value      # Agora é (Líquido + Provisões + FGTS)
    }

# ===================================================================
# LÓGICA DE CÁLCULO (PJ ATUALIZADA - FATOR R)
# ===================================================================
def calculate_pj_net_value(gross_revenue, costs=0, tax_rate_override=None):
    """
    Calcula o valor líquido PJ com OTIMIZAÇÃO TRIBUTÁRIA (Fator R).
    Compara Anexo V vs. Anexo III e escolhe o mais barato.
    """
    
    # 1. Cenário MEI (Simples e direto)
    if gross_revenue <= MEI_MONTHLY_REVENUE_LIMIT:
        regime = 'MEI'
        strategy = 'MEI (Regime Simplificado)'
        tax_amount_das = DAS_MEI_FIXED_VALUE
        pro_labore = 0
        inss_pro_labore = 0
        irrf_pro_labore = 0
        total_costs = costs + tax_amount_das
        net_value_pre_provision = gross_revenue - total_costs
    
    # 2. Cenário Simples Nacional (A Mágica do Fator R)
    else:
        regime = 'Simples Nacional'
        
        # Se usuário forçou a taxa, usamos a lógica antiga (sem otimização)
        if tax_rate_override is not None:
            strategy = f'Taxa Manual ({tax_rate_override*100:.1f}%)'
            tax_rate = tax_rate_override
            tax_amount_das = gross_revenue * tax_rate
            # Assume pró-labore mínimo para quem força a taxa
            pro_labore = MINIMUM_WAGE
            inss_pro_labore = pro_labore * 0.11
            irrf_pro_labore = 0 # IRRF é isento no salário mínimo
            
        else:
            # --- Otimização: Calcular os DOIS cenários ---
            
            # Cenário A: ANEXO V (Pró-labore Mínimo)
            pl_A = MINIMUM_WAGE
            inss_A = pl_A * 0.11
            irrf_A = 0 # Isento
            das_A = gross_revenue * ANEXO_V_RATE
            total_cost_A = das_A + inss_A + irrf_A
            net_A = gross_revenue - costs - total_cost_A
            
            # Cenário B: ANEXO III (Fator R >= 28%)
            pl_B = gross_revenue * 0.28
            inss_B = pl_B * 0.11
            irrf_B_base = pl_B - inss_B
            irrf_B = calculate_irrf(irrf_B_base) # IRRF sobre pró-labore alto
            das_B = gross_revenue * ANEXO_III_RATE
            total_cost_B = das_B + inss_B + irrf_B
            net_B = gross_revenue - costs - total_cost_B
            
            # --- Decisão do "Contador Digital" ---
            if net_B > net_A:
                # Vale a pena pagar mais INSS/IRRF para economizar no DAS
                strategy = 'Anexo III (Fator R)'
                tax_rate = ANEXO_III_RATE
                tax_amount_das = das_B
                pro_labore = pl_B
                inss_pro_labore = inss_B
                irrf_pro_labore = irrf_B
            else:
                # Mais barato ficar no Anexo V
                strategy = 'Anexo V (Pró-labore Mínimo)'
                tax_rate = ANEXO_V_RATE
                tax_amount_das = das_A
                pro_labore = pl_A
                inss_pro_labore = inss_A
                irrf_pro_labore = irrf_A
        
        total_costs = costs + tax_amount_das + inss_pro_labore + irrf_pro_labore
        net_value_pre_provision = gross_revenue - total_costs

    # 3. Calcular Provisões (Férias/13º)
    # A provisão é sobre o LÍQUIDO que sobra, não sobre o bruto.
    thirteenth_provision = net_value_pre_provision / 12
    vacation_provision = net_value_pre_provision / 12 # Simplificado (1 mês)
    total_provisions = thirteenth_provision + vacation_provision
    
    net_value_with_provisioning = net_value_pre_provision - total_provisions
    
    return {
        'regime': regime,
        'strategy': strategy,                   # NOVO
        'grossRevenue': gross_revenue,
        'costs': costs,
        'taxRate': locals().get('tax_rate', 0), # Taxa efetiva usada
        'taxAmount': tax_amount_das,            # Renomeado de taxAmount
        'proLaboreInss': inss_pro_labore,       # Renomeado de proLaboreInss
        'proLaboreIrrf': irrf_pro_labore,       # NOVO
        'netValue': net_value_pre_provision,    # Valor antes de provisões
        'thirteenthProvision': thirteenth_provision,
        'vacationProvision': vacation_provision,
        'totalProvisions': total_provisions,
        'netValueWithProvisioning': net_value_with_provisioning # Valor final comparável
    }

# ===================================================================
# LÓGICA DE DADOS (Sem mudanças)
# ===================================================================
def get_market_rate_from_csv(area, seniority, location):
    """Busca a taxa mais recente (último mês) para os cálculos principais."""
    if df_market.empty: return None
    try:
        # Filtra pelo cargo
        df_filtered = df_market[
            (df_market['area'] == area) &
            (df_market['seniority'] == seniority) &
            (df_market['location'] == location)
        ]
        
        if df_filtered.empty: return None
        
        # Ordena por data e pega o último registro (Mês 12/Atual)
        latest_data = df_filtered.sort_values('data_ref').iloc[-1]
        
        return {
            'clt': float(latest_data['clt_avg']), 
            'pj': float(latest_data['pj_avg'])
        }
    except Exception as e:
        print(f"Erro ao consultar DataFrame: {e}")
        return None

def get_historical_data_from_csv(area, seniority, location, work_mode):
    """Retorna datas, valores e a data do próximo mês para previsão."""
    if df_market.empty: return None, None, None
    
    try:
        df_filtered = df_market[
            (df_market['area'] == area) &
            (df_market['seniority'] == seniority) &
            (df_market['location'] == location)
        ].sort_values('data_ref').tail(12)
        
        if df_filtered.empty: return None, None, None

        # Formata datas (Eixo X)
        labels = df_filtered['data_ref'].dt.strftime('%b/%y').tolist()
        
        # Pega valores
        col_name = 'clt_avg' if work_mode == 'clt' else 'pj_avg'
        values = df_filtered[col_name].tolist()
        
        # Calcula o rótulo do próximo mês (para a previsão)
        last_date = df_filtered['data_ref'].iloc[-1]
        next_date = last_date + relativedelta(months=1)
        next_label = next_date.strftime('%b/%y')
        
        return labels, values, next_label
        
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return None, None, None

# ===================================================================
# "IA SIMULADA" (Sem mudanças, já compara os valores finais)
# ===================================================================

def get_financial_analysis(clt, pj, work_mode, area, seniority, market_rate):
    def f(val): return format_currency(val)
    clt_final = clt['equivalentValue']
    pj_final = pj['netValueWithProvisioning']
    frase_mercado = ""
    is_above_mercado = False
    
    if market_rate and market_rate.get('clt') and clt['grossSalary'] > 0:
        market_value = market_rate['clt']
        salary_value = clt['grossSalary']
        diferenca_mercado = salary_value - market_value
        percent_diff_mercado = (diferenca_mercado / market_value) * 100
        is_above_mercado = diferenca_mercado >= 0
        pct_abs = f"{abs(percent_diff_mercado):.0f}%"
        posicao = "acima" if is_above_mercado else "abaixo"
        
        if abs(percent_diff_mercado) < 5:
             frase_mercado = f"Seu salário CLT atual está alinhado com a média de mercado para sua função e nível."
        elif is_above_mercado:
             frase_mercado = f"Seu salário CLT atual, que já está {pct_abs} {posicao} da média, demonstra que você está em uma posição muito favorável e valorizada."
        else:
             frase_mercado = f"No entanto, seu salário CLT atual está {pct_abs} {posicao} da média de mercado, o que indica que você tem uma forte base para negociar."

    if work_mode == 'clt':
        diferenca_troca = pj_final - clt_final
        if diferenca_troca > 200:
            frase_troca = (f"A proposta PJ, mesmo provisionando benefícios, representa um ganho mensal de {f(diferenca_troca)}. "
                           f"Financeiramente, a troca é vantajosa.")
        elif diferenca_troca < -200:
            frase_troca = (f"A proposta PJ representa uma perda financeira substancial de {f(abs(diferenca_troca))} "
                           f"em comparação ao seu valor CLT atual, tornando a troca financeiramente desvantajosa.")
            if is_above_mercado:
                frase_mercado = frase_mercado.replace("demonstra que você está", "demonstra que você já está")
                frase_mercado += " Isso enfraquece a justificativa para aceitar uma proposta PJ tão inferior."
        else:
            frase_troca = (f"A proposta PJ é financeiramente equivalente ao seu valor CLT atual, com uma diferença de apenas {f(abs(diferenca_troca))}. "
                           f"A decisão deve se basear em outros fatores, como flexibilidade vs. segurança.")
    else: 
        diferenca_troca = clt_final - pj_final
        if diferenca_troca > 200:
            frase_troca = (f"A proposta CLT oferece um valor total {f(diferenca_troca)} maior que seu líquido PJ atual (com provisão). "
                           f"Financeiramente, a troca é positiva.")
        elif diferenca_troca < -200:
             frase_troca = (f"Alerta: A proposta CLT tem um valor total {f(abs(diferenca_troca))} menor que seu líquido PJ atual (com provisão). "
                            f"Na prática, você estaria aceitando uma redução para ter a segurança da CLT.")
        else:
             frase_troca = (f"A proposta CLT ({f(clt_final)}) é financeiramente equivalente "
                            f"ao seu líquido real PJ atual ({f(pj_final)}). "
                            f"A decisão de trocar a flexibilidade pela segurança depende de você.")

    return f"{frase_troca} {frase_mercado}"



def calculate_trend_prediction(prices):
    """Calcula a tendência e previsão usando Regressão Linear (NumPy) com mais granularidade."""
    if not prices or len(prices) < 2:
        return None

    x = np.arange(len(prices))
    y = np.array(prices)
    
    slope, intercept = np.polyfit(x, y, 1)
    
    forecast_value = (slope * len(prices)) + intercept
    
    # NOVAS REGRAS PARA A TENDÊNCIA
    if slope > 75: # Aumentei o limiar para "Forte"
        status = "Alta Forte"
        desc = "Consistente valorização observada. Indicadores apontam para continuidade do crescimento."
        color = "text-green-400"
    elif slope > 25: # Novo limiar para "Moderada"
        status = "Alta Moderada"
        desc = "Crescimento gradual. O mercado apresenta uma valorização constante."
        color = "text-teal-400"
    elif slope > -25: # Faixa de estabilidade mais ampla, com menção à inclinação
        if slope > 0:
            status = "Estável com Leve Alta"
            desc = "Mercado lateralizado, com uma inclinação positiva discreta."
            color = "text-gray-400" # Ou um tom de teal mais suave se preferir: "text-blue-400"
        elif slope < 0:
            status = "Estável com Leve Queda"
            desc = "Mercado lateralizado, com uma ligeira retração observada."
            color = "text-gray-400" # Ou um tom de rose mais suave: "text-pink-400"
        else:
            status = "Estável"
            desc = "Mercado lateralizado sem grandes oscilações no período."
            color = "text-gray-400"
    elif slope < -75: # Limiar para "Forte Queda"
        status = "Queda Forte"
        desc = "Retração acentuada. Fatores indicam uma pressão de baixa no mercado."
        color = "text-red-400"
    else: # Entre -25 e -75
        status = "Queda Moderada"
        desc = "Declínio gradual, com o mercado em processo de correção ou ajuste."
        color = "text-pink-400"

    return {
        'forecast': forecast_value,
        'slope': slope,
        'status': status,
        'description': desc,
        'color_class': color
    }

def get_last_12_months_labels():
    labels = []
    today = datetime.now()
    curr = today
    for _ in range(12):
        # Formato curto em PT-BR
        months_pt = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        label = f"{months_pt[curr.month]}/{str(curr.year)[2:]}"
        labels.append(label)
        
        # Subtrair um mês (lógica manual para evitar libs extras)
        month = curr.month - 1
        year = curr.year
        if month == 0:
            month = 12
            year -= 1
        curr = curr.replace(year=year, month=month, day=1)
        
    return list(reversed(labels))

def calculate_gaussian_distribution(user_value, market_mean):
    """
    Gera uma distribuição normal SIMULADA baseada na média de mercado.
    Motivo: Nosso CSV tem médias mensais, não dados individuais.
    Para comparar com a "população", simulamos a dispersão do mercado.
    """
    if not market_mean or market_mean <= 0:
        return None

    # 1. Inferência Estatística
    # Assumimos que o desvio padrão de salários numa mesma senioridade gira em torno de 18% da média.
    # (Ex: Junior ganha 5k. Alguns ganham 4k, outros 6k).
    std_dev = market_mean * 0.18 

    # 2. Cálculo do Z-Score Real
    z_score = (user_value - market_mean) / std_dev

    # 3. Cálculo do Percentil
    percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2))) * 100

    # 4. Gerar dados para o Gráfico (Bell Curve Perfeita)
    # Criamos uma faixa de -4 a +4 desvios padrão
    x_min = market_mean - (4 * std_dev)
    x_max = market_mean + (4 * std_dev)
    
    # Gerar 100 pontos para a curva ficar bem lisa
    x_axis = np.linspace(x_min, x_max, 100)
    
    # Função de Densidade de Probabilidade (PDF)
    y_axis = (1 / (std_dev * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_axis - market_mean) / std_dev) ** 2)

    # Normalizar Y (0 a 100) para o gráfico
    y_axis_norm = (y_axis / np.max(y_axis)) * 100

    # Formatação para o template
    return {
        'mean': market_mean,
        'std_dev': std_dev,
        'z_score': z_score,
        'percentile': percentile,
        'chart_x': json.dumps(x_axis.tolist()),
        'chart_y': json.dumps(y_axis_norm.tolist()),
        'user_x': user_value,
        'is_outlier': abs(z_score) > 1.96, # 95% de confiança
        'z_score_fmt': f"{z_score:+.2f}σ",
        'percentile_fmt': f"{percentile:.0f}%"
    }

# ===================================================================
# A VIEW PRINCIPAL (ATUALIZADA PARA NOVOS DADOS)
# ===================================================================

def home(request):
    context = {
        'result': None,
        'clt_bruto': None,
        'pj_bruto': None,
        'beneficios_extras': None,
        'pj_costs': None,
        'work_mode': 'clt',
        'areas_list': AREAS_LIST,
        'seniorities_list': SENIORITIES_LIST,
        'locations_list': LOCATIONS_LIST,
        'selected_area': '',
        'selected_seniority': '',
        'selected_location': '',
        'mei_limit': MEI_MONTHLY_REVENUE_LIMIT,
        'pj_tax_rate_override': '',
    }

    if request.method == 'POST':
        try:
            area = request.POST.get('area', '')
            seniority = request.POST.get('seniority', '')
            location = request.POST.get('location', '')
            clt_bruto_str = request.POST.get('clt_bruto', '0')
            pj_bruto_str = request.POST.get('pj_bruto', '0')
            beneficios_extras_str = request.POST.get('beneficios_extras', '0')
            pj_costs_str = request.POST.get('pj_costs', '0')
            work_mode = request.POST.get('work_mode', 'clt')
            
            pj_tax_rate_override_str = request.POST.get('pj_tax_rate_override', '')
            pj_tax_rate_override_num = float(pj_tax_rate_override_str) / 100 if pj_tax_rate_override_str else None

            clt_bruto = float(clt_bruto_str) if clt_bruto_str else 0
            pj_bruto = float(pj_bruto_str) if pj_bruto_str else 0
            beneficios_extras = float(beneficios_extras_str) if beneficios_extras_str else 0
            pj_costs = float(pj_costs_str) if pj_costs_str else 0

            # Validações (sem mudança)
            if not area or not seniority or not location:
                context['error'] = 'Por favor, preencha seu contexto profissional para uma análise completa.'
                return render(request, 'index.html', context)
            if clt_bruto <= 0 or pj_bruto <= 0:
                context['error'] = 'Por favor, insira valores válidos e positivos para salário e faturamento.'
                context['selected_area'] = area
                context['selected_seniority'] = seniority
                context['selected_location'] = location
                return render(request, 'index.html', context)

            # --- NOVOS CÁLCULOS ---
            clt_result = calculate_clt_equivalent_monthly_value(clt_bruto, beneficios_extras)
            pj_result = calculate_pj_net_value(pj_bruto, pj_costs, pj_tax_rate_override_num)
            
            market_rate = get_market_rate_from_csv(area, seniority, location)
            
            # 2. Busca histórico REAL para o gráfico (NOVO)
            trend_data = None
            # Agora desempacotamos 3 valores: labels, valores e o label futuro
            hist_labels, hist_values, next_label = get_historical_data_from_csv(area, seniority, location, work_mode)
            
            if hist_labels and hist_values:
                prediction = calculate_trend_prediction(hist_values)
                
                if prediction:
                    # Converter previsão para float nativo do Python (evita erros com NumPy)
                    forecast_val = float(prediction['forecast'])
                    
                    # Série 1: Histórico (12 meses)
                    # Série 2: Previsão (Conecta o último ponto histórico ao futuro)
                    # [None, None, ..., Valor_Dez, Valor_Jan_Prev]
                    pred_series = [None] * (len(hist_values) - 1) + [hist_values[-1], forecast_val]
                    
                    trend_data = {
                        # JSON Dumps garante que [None] vire [null] para o JavaScript
                        'chart_categories': json.dumps(hist_labels + [next_label]),
                        'series_historical': json.dumps(hist_values),
                        'series_prediction': json.dumps(pred_series),
                        'chart_series_name': json.dumps(f"Histórico {work_mode.upper()} - {area}"),
                        
                        # Dados do Card de Insight (Strings normais, não precisa de dumps)
                        'forecast_value_f': format_currency(forecast_val),
                        'insight_title': prediction['status'],
                        'insight_desc': prediction['description'],
                        'insight_color': prediction['color_class'],
                        'slope': prediction['slope']
                    }

            # Gera análise textual
            analysis_text = get_financial_analysis(clt_result, pj_result, work_mode, area, seniority, market_rate)
            diferenca_final = pj_result['netValueWithProvisioning'] - clt_result['equivalentValue']

            stats_data = None
            
            if market_rate and market_rate.get('clt'):
                # O usuário pediu para focar apenas na comparação CLT vs Mercado CLT
                # Pois PJ tem muitas variáveis (impostos, benefícios) que distorcem a curva.
                
                market_mean_stats = market_rate['clt'] # Sempre compara com a média CLT
                user_val_stats = clt_bruto # Sempre usa o valor CLT inputado
                
                # Define o rótulo correto baseado no contexto
                if work_mode == 'clt':
                    user_label = "CLT Atual"
                else:
                    user_label = "Proposta CLT"
                
                # Chama a função de cálculo
                stats_data = calculate_gaussian_distribution(user_val_stats, market_mean_stats)
                
                if stats_data:
                    stats_data['user_label'] = user_label
            
            # Monta o contexto final
            result_data = {
                'clt': clt_result,
                'pj': pj_result,
                'analysis': analysis_text,
                'marketRate': market_rate,
                'statistics': stats_data,
                'trend': trend_data,  # <--- Gráfico com dados reais
                'diferenca': diferenca_final,
                
                # ... (Mantenha os format_currency existentes: clt_equivalent_formatted, etc.)
                'clt_equivalent_formatted': format_currency(clt_result['equivalentValue']),
                'pj_real_formatted': format_currency(pj_result['netValueWithProvisioning']),
                'fgts_formatted': format_currency(clt_result['fgtsMonthly']),
                'diferenca_formatted': format_currency(abs(diferenca_final)),
                
                'clt_gross_f': format_currency(clt_result['grossSalary']),
                'clt_inss_f': format_currency(clt_result['inssDiscount']),
                'clt_irrf_f': format_currency(clt_result['irrfDiscount']),
                'clt_net_f': format_currency(clt_result['netSalary']),
                'clt_benefits_f': format_currency(clt_result['extraBenefits']),
                'clt_thirteenth_f': format_currency(clt_result['thirteenthMonthly']),
                'clt_vacation_f': format_currency(clt_result['vacationMonthly']),
                'clt_fgts_f': format_currency(clt_result['fgtsMonthly']),
                'clt_total_f': format_currency(clt_result['equivalentValue']),
                
                'pj_revenue_f': format_currency(pj_result['grossRevenue']),
                'pj_costs_f': format_currency(pj_result['costs']),
                'pj_tax_f': format_currency(pj_result['taxAmount']),
                'pj_tax_rate_f': f"{pj_result['taxRate'] * 100:.1f}%",
                'pj_pro_labore_inss_f': format_currency(pj_result['proLaboreInss']),
                'pj_pro_labore_irrf_f': format_currency(pj_result['proLaboreIrrf']),
                'pj_net_pre_provision_f': format_currency(pj_result['netValue']),
                'pj_provisions_f': format_currency(pj_result['totalProvisions']),
                'pj_total_f': format_currency(pj_result['netValueWithProvisioning']),
            }
            
            if market_rate:
                # Lógica do benchmark (sem mudanças)
                proposal_num = clt_result['grossSalary']
                market_num = market_rate['clt']
                percentage_diff = ((proposal_num - market_num) / market_num) * 100
                is_above = percentage_diff >= 0
                if proposal_num > market_num:
                    proposal_width = 95
                    market_width = (market_num / proposal_num) * 95 if proposal_num > 0 else 0
                else:
                    market_width = 95
                    proposal_width = (proposal_num / market_num) * 95 if market_num > 0 else 0
                
                result_data['benchmark'] = {
                    'proposal_val_f': format_currency(proposal_num),
                    'market_val_f': format_currency(market_num),
                    'percentageDiff': f"{percentage_diff:.0f}",
                    'is_above': is_above,
                    'proposal_width': f"{proposal_width:.2f}",
                    'market_width': f"{market_width:.2f}",
                }

            context['result'] = result_data
            context['clt_bruto'] = clt_bruto
            context['pj_bruto'] = pj_bruto
            context['beneficios_extras'] = beneficios_extras
            context['pj_costs'] = pj_costs
            context['work_mode'] = work_mode
            context['selected_area'] = area
            context['selected_seniority'] = seniority
            context['selected_location'] = location
            context['pj_tax_rate_override'] = pj_tax_rate_override_str 

        except (ValueError, TypeError) as e:
            print(e)
            context['error'] = "Ocorreu um erro ao processar os valores. Tente novamente."

    return render(request, 'index.html', context)