# core/views.py (VERSÃO CORRIGIDA - LÓGICA DO GRÁFICO MOVIDA PARA A VIEW)

from django.shortcuts import render
import math
import pandas as pd
import os

# ===================================================================
# CARREGAR A BASE DE DADOS
# ===================================================================
try:
    CSV_PATH = os.path.join(os.path.dirname(__file__), 'salarios_mercado.csv')
    df_market = pd.read_csv(CSV_PATH)
    AREAS_LIST = sorted(df_market['area'].unique())
    SENIORITIES_LIST = ['Júnior', 'Pleno', 'Sênior']
    LOCATIONS_LIST = sorted(df_market['location'].unique())
except FileNotFoundError:
    print("ERRO: 'salarios_mercado.csv' não encontrado na pasta 'core'.")
    df_market = pd.DataFrame() 
    AREAS_LIST = ['Desenvolvimento de Software', 'Marketing Digital', 'Design de Produto (UI/UX)']
    SENIORITIES_LIST = ['Júnior', 'Pleno', 'Sênior']
    LOCATIONS_LIST = ['São Paulo - SP', 'Rio de Janeiro - RJ', 'Santa Catarina - SC']

# ===================================================================
# FUNÇÃO DE FORMATAÇÃO
# ===================================================================
def format_currency(value):
    try:
        val_str = f"{value:,.2f}"
        return f"R$ {val_str.replace(',', 'X').replace('.', ',').replace('X', '.')}"
    except (ValueError, TypeError):
        return "R$ 0,00"

# ===================================================================
# LÓGICA DE CÁLCULO (Sem mudanças)
# ===================================================================

def calculate_clt_equivalent_monthly_value(gross_salary, extra_benefits=0):
    thirteenth_monthly = gross_salary / 12
    vacation_monthly = gross_salary / 12
    vacation_bonus_monthly = (gross_salary / 3) / 12
    fgts_monthly = gross_salary * 0.08
    total_benefits_monthly = (thirteenth_monthly + vacation_monthly + vacation_bonus_monthly + fgts_monthly)
    equivalent_value = gross_salary + total_benefits_monthly + extra_benefits
    return {'grossSalary': gross_salary, 'extraBenefits': extra_benefits, 'thirteenthMonthly': thirteenth_monthly, 'vacationMonthly': vacation_monthly, 'vacationBonusMonthly': vacation_bonus_monthly, 'fgtsMonthly': fgts_monthly, 'totalBenefitsMonthly': total_benefits_monthly, 'equivalentValue': equivalent_value}

def get_simples_nacional_tax_rate(monthly_revenue):
    if monthly_revenue <= 15000: return 0.06
    if monthly_revenue <= 30000: return 0.112
    if monthly_revenue <= 60000: return 0.135
    if monthly_revenue <= 150000: return 0.16
    if monthly_revenue <= 300000: return 0.21
    return 0.33

def calculate_pj_net_value(gross_revenue, costs=0):
    taxable_revenue = gross_revenue - costs
    tax_rate = get_simples_nacional_tax_rate(gross_revenue)
    tax_amount = gross_revenue * tax_rate
    net_value = taxable_revenue - tax_amount
    thirteenth_provision = taxable_revenue / 12
    vacation_provision = taxable_revenue / 12
    total_provisions = thirteenth_provision + vacation_provision
    net_value_with_provisioning = net_value - total_provisions
    return {'grossRevenue': gross_revenue, 'costs': costs, 'taxableRevenue': taxable_revenue, 'taxRate': tax_rate, 'taxAmount': tax_amount, 'netValue': net_value, 'thirteenthProvision': thirteenth_provision, 'vacationProvision': vacation_provision, 'totalProvisions': total_provisions, 'netValueWithProvisioning': net_value_with_provisioning}

# ===================================================================
# LÓGICA DE DADOS (Sem mudanças)
# ===================================================================
def get_market_rate_from_csv(area, seniority, location):
    if df_market.empty:
        return None
    try:
        rate = df_market[
            (df_market['area'] == area) &
            (df_market['seniority'] == seniority) &
            (df_market['location'] == location)
        ]
        if not rate.empty:
            rate_data = rate.iloc[0]
            return {'clt': rate_data['clt_avg'], 'pj': rate_data['pj_avg']}
        return None
    except Exception as e:
        print(f"Erro ao consultar DataFrame: {e}")
        return None

# ===================================================================
# "IA SIMULADA" (Sem mudanças)
# ===================================================================
def get_financial_analysis(clt, pj, work_mode, area, seniority, market_rate):
    def f(val): return format_currency(val)

    clt_final = clt['equivalentValue']
    pj_final = pj['netValueWithProvisioning']
    veredicto_troca = ""
    if work_mode == 'clt':
        diferenca = pj_final - clt_final
        if diferenca > 200:
            veredicto_troca = (f"A proposta PJ, mesmo provisionando benefícios, representa um ganho mensal de {f(diferenca)}. Financeiramente, a troca é vantajosa.")
        elif diferenca < -200:
            veredicto_troca = (f"Alerta: A proposta PJ tem um valor líquido (com provisão) {f(abs(diferenca))} menor que seu valor CLT atual. Na prática, você estaria aceitando uma redução.")
        else:
            veredicto_troca = (f"A troca é financeiramente equivalente. O valor líquido provisionado do PJ é muito próximo ao seu valor CLT atual.")
    else: 
        diferenca = clt_final - pj_final
        if diferenca < -200:
            veredicto_troca = (f"Alerta: A proposta CLT tem um valor total {f(abs(diferenca))} menor que seu líquido PJ atual (com provisão). Financeiramente, não parece ser uma boa troca.")
        elif diferenca > 200:
            veredicto_troca = (f"A proposta CLT é vantajosa, oferecendo {f(diferenca)} a mais em valor total do que seu líquido PJ atual (com provisão).")
        else:
            veredicto_troca = (f"A proposta CLT é financeiramente equivalente ao seu líquido PJ (com provisão). A decisão depende de fatores não-financeiros.")

    analise_mercado = ""
    if market_rate and market_rate.get('clt') and clt['grossSalary'] > 0:
        market_value = market_rate['clt']
        salary_value = clt['grossSalary']
        diferenca_mercado = salary_value - market_value
        percent_diff = (diferenca_mercado / market_value) * 100
        is_above = diferenca_mercado >= 0
        analise_mercado = (f"A média de mercado para uma vaga CLT similar é de {f(market_value)}. Seu salário CLT está {abs(percent_diff):.0f}% {'ACIMA' if is_above else 'ABAIXO'} da média.")
    else:
        analise_mercado = "Não foi possível obter uma média de mercado para seu contexto CLT."

    return f"{veredicto_troca} {analise_mercado}"

# ===================================================================
# A VIEW PRINCIPAL (COM A LÓGICA DO GRÁFICO)
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

            clt_bruto = float(clt_bruto_str) if clt_bruto_str else 0
            pj_bruto = float(pj_bruto_str) if pj_bruto_str else 0
            beneficios_extras = float(beneficios_extras_str) if beneficios_extras_str else 0
            pj_costs = float(pj_costs_str) if pj_costs_str else 0

            if not area or not seniority or not location:
                context['error'] = 'Por favor, preencha seu contexto profissional para uma análise completa.'
                return render(request, 'index.html', context)
            if clt_bruto <= 0 or pj_bruto <= 0:
                context['error'] = 'Por favor, insira valores válidos e positivos para salário e faturamento.'
                context['selected_area'] = area
                context['selected_seniority'] = seniority
                context['selected_location'] = location
                return render(request, 'index.html', context)

            clt_result = calculate_clt_equivalent_monthly_value(clt_bruto, beneficios_extras)
            pj_result = calculate_pj_net_value(pj_bruto, pj_costs)
            market_rate = get_market_rate_from_csv(area, seniority, location)
            analysis_text = get_financial_analysis(clt_result, pj_result, work_mode, area, seniority, market_rate)
            diferenca_final = pj_result['netValueWithProvisioning'] - clt_result['equivalentValue']
            
            result_data = {
                'clt': clt_result,
                'pj': pj_result,
                'analysis': analysis_text,
                'marketRate': market_rate,
                'diferenca': diferenca_final,
                'clt_equivalent_formatted': format_currency(clt_result['equivalentValue']),
                'pj_real_formatted': format_currency(pj_result['netValueWithProvisioning']),
                'fgts_formatted': format_currency(clt_result['fgtsMonthly']),
                'diferenca_formatted': format_currency(abs(diferenca_final)),
            }
            
            # --- NOVA LÓGICA DO GRÁFICO ---
            if market_rate:
                proposal_num = clt_result['grossSalary']
                market_num = market_rate['clt']
                
                percentage_diff = ((proposal_num - market_num) / market_num) * 100
                is_above = percentage_diff >= 0
                
                # Normaliza as barras para 95% do espaço
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
            # --- FIM DA LÓGICA DO GRÁFICO ---

            context['result'] = result_data
            context['clt_bruto'] = clt_bruto
            context['pj_bruto'] = pj_bruto
            context['beneficios_extras'] = beneficios_extras
            context['pj_costs'] = pj_costs
            context['work_mode'] = work_mode
            context['selected_area'] = area
            context['selected_seniority'] = seniority
            context['selected_location'] = location

        except (ValueError, TypeError) as e:
            print(e)
            context['error'] = "Ocorreu um erro ao processar os valores. Tente novamente."

    return render(request, 'index.html', context)