import pytesseract
from PIL import ImageGrab, Image, ImageEnhance, ImageTk, ImageStat
import tkinter as tk
import tkinter.font as tkFont # importa as fontes
from tkinter import ttk  # Adicione esta linha para importar o ttk
from tkinter import messagebox, PhotoImage
import re
import threading  # Importando threading para executar tarefas em paralelo
import sys
import locale
import cv2  # Importação do OpenCV
locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
import os
import logging
import pyautogui

"""# Configuração do logging
logging.basicConfig(
    filename='erro_log.txt',  # O nome do arquivo de log
    level=logging.DEBUG,      # Registra mensagens de DEBUG ou mais graves
    format='%(asctime)s - %(levelname)s - %(message)s',  # Formato das mensagens
)"""
# Verifica se está rodando como executável (PyInstaller)
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS  # Pasta temporária do PyInstaller
else:
    base_path = os.path.dirname(__file__)  # Modo normal (Python)

# Caminho do Tesseract dentro do pacote
tesseract_path = os.path.join(base_path, 'Tesseract-OCR', 'tesseract.exe')

# Define o caminho do Tesseract para o pytesseract
import pytesseract
pytesseract.pytesseract.tesseract_cmd = tesseract_path

# Inicializa a variável total_acumulado fora das funções
total_acumulado = 0.0
# Configuração personalizada para o Tesseract
config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789R$.,- '

def selecionar_area(canvas, root):
    """
    Permite ao usuário selecionar uma área da tela com retângulo dinâmico.
    Retorna as coordenadas absolutas da região (x1, y1, x2, y2).
    """
    def iniciar_selecao(event):
        global start_x, start_y, rect_id
        # Obtém coordenadas absolutas do mouse
        start_x, start_y = root.winfo_pointerx(), root.winfo_pointery()
        rect_id = canvas.create_rectangle(start_x, start_y, start_x, start_y, outline="#E2A40C", width=2)

    def ajustar_retangulo(event):
        # Atualiza coordenadas do retângulo
        end_x, end_y = root.winfo_pointerx(), root.winfo_pointery()
        canvas.coords(rect_id, start_x, start_y, end_x, end_y)

    def finalizar_selecao(event):
        global end_x, end_y
        end_x, end_y = root.winfo_pointerx(), root.winfo_pointery()
        root.quit()  # Fecha a janela de seleção

    global rect_id
    rect_id = None

    canvas.bind("<Button-1>", iniciar_selecao)
    canvas.bind("<B1-Motion>", ajustar_retangulo)
    canvas.bind("<ButtonRelease-1>", finalizar_selecao)

    root.mainloop()  # Mantém a interface aberta até a seleção ser concluída

    return (start_x, start_y, end_x, end_y)

def capturar_area(escalar=2):
    """
    Captura a área da tela selecionada pelo usuário e retorna a imagem.
    Ajusta automaticamente para diferentes resoluções de tela.
    """
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.1)
    root.configure(bg="gray")

    canvas = tk.Canvas(root, cursor="cross", bg="gray", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    x1, y1, x2, y2 = selecionar_area(canvas, root)  # Função que captura a seleção do usuário

    # Obtém a resolução atual da tela
    largura_tela, altura_tela = pyautogui.size()
    largura_ref = 1920  # Resolução base usada no desenvolvimento
    altura_ref = 1080

    # Calcula o fator de ajuste para diferentes resoluções
    fator_x = largura_tela / largura_ref
    fator_y = altura_tela / altura_ref

    # Ajusta as coordenadas para a tela atual
    x1 = int(x1 * fator_x)
    y1 = int(y1 * fator_y)
    x2 = int(x2 * fator_x)
    y2 = int(y2 * fator_y)

    # Captura a tela com as novas coordenadas
    region = (x1, y1, x2, y2)
    imagem = ImageGrab.grab(bbox=region)

    # Aplicando escalonamento para melhorar a qualidade
    largura, altura = imagem.size
    imagem = imagem.resize((largura * escalar, altura * escalar), Image.LANCZOS)
    """imagem.save('imagem_salva.png')"""

    return imagem

def melhorar_imagem(imagem):
    """
    Melhora a qualidade da imagem para OCR.
    """
    try:
        if not imagem or ImageStat.Stat(imagem).sum[0] == 0:
            return imagem
        enhancer = ImageEnhance.Contrast(imagem)
        imagem = enhancer.enhance(2.0)
        """imagem.save('imagem_salva_melhorada.png')"""
        return imagem
    
    except Exception as e:
        print(f"Erro ao melhorar a imagem: {e}")
        return imagem



def ajustar_fragmentos(valores):
    """
    Junta tokens fragmentados que não iniciam com 'R$' ao token anterior.
    Exemplo:
        ['R$ 4.305,00', 'R$ 1.244,00', 'R$ 2.398', '11']
    torna-se:
        ['R$ 4.305,00', 'R$ 1.244,00', 'R$ 2.398/11']
    """
    novos = []
    for token in valores:
        token = token.strip()
        if token.startswith("R$"):
            novos.append(token)
        else:
            if novos:
                novos[-1] = novos[-1] + "/" + token
            else:
                novos.append(token)
    return novos

def corrigir_valores(valores):
    """
    Corrige os valores monetários:
    - Ajusta fragmentos que foram extraídos separadamente.
    - Substitui barras (/) por vírgulas, pois a barra deve ser um separador decimal.
    - Remove o símbolo 'R$' e espaços extras.
    - Trata valores com múltiplos separadores (pontos de milhar e vírgula decimal), removendo pontos desnecessários e convertendo a vírgula em ponto.
    - Para valores sem separador, assume que os dois últimos dígitos representam os centavos.
    - Retorna os valores numéricos em formato adequado para cálculos.
    """
    # Primeiro, ajustar fragmentos para unir tokens quebrados
    valores = ajustar_fragmentos(valores)
    
    valores_corrigidos = []
    
    for valor in valores:
        # Substituir a barra por vírgula (caso a barra represente o separador decimal)
        valor = valor.replace("/", ",")
    
        # Remover "R$" e espaços extras
        valor = valor.replace("R$", "").replace(" ", "")
    
        # Tratar valores negativos
        negativo = valor.startswith("-")
        if negativo:
            valor = valor[1:]
    
        # Caso o valor contenha ambos os separadores (ponto e vírgula)
        if "." in valor and "," in valor:
            if valor.rfind(",") > valor.rfind("."):
                # Formato típico (1.000,00): Remove os pontos de milhar
                partes = valor.split(",")
                valor = "".join(partes[:-1]).replace(".", "") + "." + partes[-1]
            else:
                # Formato atípico (1,000.00): Remove as vírgulas de milhar
                partes = valor.split(".")
                valor = "".join(partes[:-1]).replace(",", "") + "." + partes[-1]
        elif "." in valor and valor.count(".") > 1:
            # Para números grandes com múltiplos pontos (ex: 1.234.567): mantém apenas o último como separador decimal
            partes = valor.split(".")
            valor = "".join(partes[:-1]) + "." + partes[-1]
        elif "," in valor:
            # Formato simples com vírgula decimal (ex: 344,15 ou 7,16): substituir vírgula por ponto
            valor = valor.replace(",", ".")
        elif valor.isdigit() and len(valor) > 2:
            # Para valores sem separador (ex: "34415" deve ser interpretado como "344.15")
            valor = valor[:-2] + "." + valor[-2:]
    
        # Adicionar o sinal negativo se necessário
        if negativo:
            valor = "-" + valor
    
        valores_corrigidos.append(valor)
    
    return valores_corrigidos

def validar_valor(valor):
    """
    Valida se o valor está no formato correto.
    """
    return re.match(r"^-?\d+\.\d{2}$", valor) is not None

def extrair_valores_da_imagem(imagem):
    """
    Realiza OCR e extrai valores monetários.
    """
    texto = pytesseract.image_to_string(imagem, lang="por", config="--psm 6")
    print(f"Texto extraído:\n{texto}")

    padrao_valores = r"R\$\s*-?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|R\$\s*-?\s*\d+(?:[.,]\d{2})?"
    valores = re.findall(padrao_valores, texto)
    print(f"Valores encontrados: {valores}")

    valores_corrigidos = corrigir_valores(valores)
    print(f"Valores corrigidos: {valores_corrigidos}")

    valores_limpos = []
    for valor in valores_corrigidos:
        if validar_valor(valor):
            valores_limpos.append(float(valor))
        else:
            print(f"Valor inválido ignorado: {valor}")

    return valores_limpos

def somar_valores(valores):
    """
    Soma os valores extraídos.
    :param valores: Lista de valores numéricos.
    :return: Soma dos valores.
    """
    return sum(valores)

def adicionar_valores(resultados_label, soma_label):
    """
    Função que adiciona os valores extraídos ao total acumulado.
    """
    def tarefa_em_thread():
        global total_acumulado  # Declara que estamos usando a variável global
        try:
            """" print(f"Total Acumulado antes da soma: {total_acumulado}")  # Debug: Verifique o valor antes da soma"""
            
            # Captura e processa os valores como antes
            imagem = capturar_area(escalar=3)  # Aumente o valor de 'escalar' para melhorar a qualidade
            valores_extraidos = extrair_valores_da_imagem(imagem)
            
            # Exibir resultados
            atualizar_interface(resultados_label, soma_label, valores_extraidos)
            
            # Processar soma extraída
            soma_extraida = sum([float(str(valor).replace(",", ".").strip()) for valor in valores_extraidos if str(valor).strip().replace(",", "").replace(".", "").isdigit()])
            
            # Somar ao total acumulado
            total_acumulado += soma_extraida
            
            """"print(f"Soma extraída: {soma_extraida}")  # Debug: Verifique a soma extraída
            print(f"Total Acumulado após a soma: {total_acumulado}")  # Debug: Verifique o valor após a soma """
            
            # Atualiza o rótulo da soma total
            soma_label.config(text=f"Soma Total: R$ {total_acumulado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
            
            # Atualizar o total na interface
            soma_label.config(text=f"Soma Total: {total_acumulado:.2f}")
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
    
    # Rodando a tarefa em uma thread para não bloquear a interface
    threading.Thread(target=tarefa_em_thread).start()
    
def atualizar_interface(resultados_label, soma_label, valores_extraidos):
    """
    Atualiza a interface com a lista de valores extraídos e a soma total.
    :param resultados_label: Label onde será mostrada a lista de valores.
    :param soma_label: Label onde será mostrada a soma total.
    :param valores_extraidos: Lista de valores extraídos.
    """
    if not isinstance(valores_extraidos, list):
        raise ValueError("O parâmetro 'valores_extraidos' deve ser uma lista.")

    if valores_extraidos:
        try:
            # Formatar os valores conforme o padrão brasileiro
            valores_formatados = [locale.format_string("R$ %.2f", v, grouping=True) for v in valores_extraidos]
            resultados_label.config(text="Valores extraídos:\n" + "\n".join(valores_formatados))

            # Calcular e formatar a soma total
            soma_total = somar_valores(valores_extraidos)
            soma_label.config(text=locale.format_string("Soma total: R$ %.2f", soma_total, grouping=True))
        except (TypeError, ValueError) as e:
            messagebox.showerror("Erro de formatação", f"Erro ao formatar valores: {e}")
    else:
        resultados_label.config(text="Nenhum valor encontrado.")
        soma_label.config(text="Soma total: R$ 0,00")

def somar_club_vip(resultados_label, soma_label):
    """
    Função para capturar a área e somar os valores extraídos para "Club VIP".
    """
    def tarefa_em_thread():
        global total_acumulado  # Declara a variável global para poder modificá-la
        try:
            imagem = capturar_area(escalar=3)  # Aumente o valor de 'escalar' para melhorar a qualidade
            valores_extraidos = extrair_valores_da_imagem(imagem)
            
            # Certifique-se de que a função somar_valores está definida e retorna um valor
            somar_valores = sum(valores_extraidos)  # Exemplo: soma os valores da lista
            
            # Atualiza a variável global total_acumulado
            total_acumulado += somar_valores
            
            # Atualiza a interface com os valores extraídos e o total acumulado
            atualizar_interface(resultados_label, soma_label, valores_extraidos)
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro: {e}")

    # Inicia a tarefa de forma assíncrona para não bloquear a interface
    thread = threading.Thread(target=tarefa_em_thread)
    thread.start()
    
def formatar_real(valor): # Definindo a função formatar_real
    """
    Função para formatar valores como moeda no formato R$ X.XXX,XX
    """
    try:
        valor_formatado = f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return valor_formatado
    except ValueError:
        return "R$ 0,00"
def limpar(resultados_label, soma_label):
    """
    Função para limpar todos os dados da calculadora, tanto visualmente quanto internamente.
    """
    global total_acumulado  # Declara a variável global para poder modificá-la

    # Reseta a variável global
    total_acumulado = 0

    # Limpa os labels da interface
    resultados_label.config(text="Nenhum valor encontrado.")
    soma_label.config(text="Soma total: R$ 0,00")

    # Adicione aqui outras variáveis que precisam ser resetadas, se houver
    # Exemplo: outras_variavel = 0

def somar_ggr_positivo(resultados_label, soma_label):
    """
    Função para capturar a área e somar os valores extraídos para "GGR".
    A soma é ajustada conforme a lógica:
    Depósito - Saques - GGR (se GGR for positivo)
    Depósito - Saques + GGR (se GGR for negativo)
    """
    def tarefa_em_thread():
        global total_acumulado  # Declara a variável global para poder modificá-la
        try:
            imagem = capturar_area(escalar=3)  # Aumente o valor de 'escalar' para melhorar a qualidade
            valores_extraidos = extrair_valores_da_imagem(imagem)

            if valores_extraidos:
                deposito = valores_extraidos[0]  # Supondo que o primeiro valor seja o depósito
                saques = valores_extraidos[1]  # O segundo valor seja o saque
                ggr = valores_extraidos[2] if len(valores_extraidos) > 2 else 0  # O terceiro valor é o GGR

                # Lógica de soma/subtração
                if ggr < 0:  # Se GGR for negativo, somamos o valor absoluto de GGR
                    resultado = deposito - saques + abs(ggr)
                else:  # Se GGR for positivo, subtraímos o valor de GGR
                    resultado = deposito - saques - ggr

                # Atualiza a variável global total_acumulado
                total_acumulado += resultado

                # Atualiza a interface
                resultados_label.config(text=f"Valores extraídos:\nDepósito: {formatar_real(deposito)}\nSaques: {formatar_real(saques)}\nGGR: {formatar_real(ggr)}")
                soma_label.config(text=f"Soma total: {formatar_real(resultado)}")
            else:
                resultados_label.config(text="Nenhum valor encontrado.")
                soma_label.config(text="Soma total: R$ 0,00")
        except Exception as e:
            print(f"Erro ao somar GGR: {e}")
            resultados_label.config(text="Erro ao processar valores.")
            soma_label.config(text="Soma total: R$ 0,00")

    # Inicia a tarefa de forma assíncrona para não bloquear a interface
    thread = threading.Thread(target=tarefa_em_thread)
    thread.start()
def somar_ggr_negativo(resultados_label, soma_label):
    """
    Função para capturar a área e somar os valores extraídos para "GGR".
    A soma é ajustada conforme a lógica:
    Depósito - Saques + GGR (se GGR for negativo)
    Depósito - Saques - GGR (se GGR for positivo)
    """
    def tarefa_em_thread():
        global total_acumulado  # Declara a variável global para poder modificá-la
        try:
            imagem = capturar_area(escalar=3)  # Aumente o valor de 'escalar' para melhorar a qualidade
            valores_extraidos = extrair_valores_da_imagem(imagem)

            if valores_extraidos:
                deposito = valores_extraidos[0]  # Supondo que o primeiro valor seja o depósito
                saques = valores_extraidos[1]  # O segundo valor seja o saque
                ggr = valores_extraidos[2] if len(valores_extraidos) > 2 else 0  # O terceiro valor é o GGR

                # Lógica de soma/subtração (mantida conforme você enviou)
                resultado = deposito - saques + ggr  # Sempre somar GGR (se for negativo, usamos o valor positivo)

                # Atualiza a variável global total_acumulado
                total_acumulado += resultado

                # Atualiza a interface
                resultados_label.config(text=f"Valores extraídos:\nDepósito: {formatar_real(deposito)}\nSaques: {formatar_real(saques)}\nGGR: {formatar_real(ggr)}")
                soma_label.config(text=f"Soma total: {formatar_real(resultado)}")
            else:
                resultados_label.config(text="Nenhum valor encontrado.")
                soma_label.config(text="Soma total: R$ 0,00")
        except Exception as e:
            print(f"Erro ao somar GGR: {e}")
            resultados_label.config(text="Erro ao processar valores.")
            soma_label.config(text="Soma total: R$ 0,00")

    # Inicia a tarefa de forma assíncrona para não bloquear a interface
    thread = threading.Thread(target=tarefa_em_thread)
    thread.start()
# Interface Gráfica
def setup_icone(root):
    # Verifica se o aplicativo está empacotado
    if getattr(sys, 'frozen', False):
        # Se estiver empacotado, usa o diretório onde o executável está
        icon_path = os.path.join(sys._MEIPASS, 'imagens/icon.ico')
    else:
        # Caso contrário, usa o diretório de desenvolvimento
        icon_path = 'imagens/icon.ico'

    # Configura o ícone da janela
    root.wm_iconbitmap(icon_path)

def criar_interface():
    """
    Cria a interface gráfica da aplicação.
    """
    app = tk.Tk()
    app.title("Calculadora de GGR")
    app.geometry("450x600")
    app.resizable(True, True)
    app.config(bg="#151521")
    
    # Definir o ícone para a janela
    setup_icone(app)

    # Fonte personalizada em negrito e branco
    font_poppins = tkFont.Font(family="Poppins", size=10, weight="bold")
    # Cor de fundo
    cor_fundo = "#1E1E2D"  # Cor de fundo personalizada

    # Definir estilo da Scrollbar
    style = ttk.Style()
    style.theme_use("clam")  # Tema mais personalizável
    style.configure("Vertical.TScrollbar",
        gripcount=0,
        background="grey",  # Cor da barra
        troughcolor="#212121",  # Cor do "trilho"
        bordercolor="#1E1E2D",  # Cor da Borda
        arrowcolor="#0D0D0D", # Cor da Flecha
        relief="flat",
        borderwidth=0,
        padding=50, # Simula arredondamento
    )
    # Arredondando a barra de rolagem com padding
    style.configure("TScrollbar",
                    borderwidth=0,
                    relief="flat",
                    padding=5)  # Simula arredondamento
    style.map(
    "Vertical.TScrollbar",
    background=[("pressed", "#555555"), ("active", "#444444")],  # Opção hover personalizada
    arrowcolor=[("pressed", "#FFFFFF"), ("active", "#FFFFFF")],  # Evitar mudança visual nas setas
    )

    # Frame principal para centralizar os widgets
    frame_principal = tk.Frame(app, bg=cor_fundo)
    frame_principal.pack(expand=True, fill="both", padx=10, pady=10)

    # Adicionar os Labels para mostrar os resultados com uma barra de rolagem
    label_titulo = tk.Label(frame_principal, text="VALORES EXTRAIDOS:", font=font_poppins, background=cor_fundo, fg="white")
    label_titulo.pack(pady=10)

    # Frame com Scrollbar (retângulo com valores extraídos)
    frame_scroll = tk.Frame(frame_principal, bg=cor_fundo, height=150, width=400)
    frame_scroll.pack(pady=(0, 10))  # Adicionado padding inferior
    frame_scroll.pack_propagate(False)  # Impede o redimensionamento automático

    canvas = tk.Canvas(frame_scroll, bg=cor_fundo, highlightthickness=0)
    scrollbar = ttk.Scrollbar(frame_scroll, orient="vertical", command=canvas.yview, style="Vertical.TScrollbar")
    scrollable_frame = tk.Frame(canvas, bg=cor_fundo)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    resultados_label = tk.Label(scrollable_frame, text="", font=font_poppins, background=cor_fundo, fg="white", justify=tk.LEFT)
    resultados_label.pack(anchor="w", fill="both", expand=True)

    # Soma total
    soma_label = tk.Label(frame_principal, text="Soma total: R$ 0.00", font=font_poppins, background=cor_fundo, fg="white",)
    soma_label.place(x=20, y=200, width=400, height=40)
    
    # Botão para adicionar valor 
    btn_adicionar_valor = tk.Button(
        frame_principal,
        text="Add Valores",
        font=font_poppins,
        command=lambda: adicionar_valores(resultados_label, soma_label),
        bg="#E2A40C",
        fg="white"
    )
    btn_adicionar_valor.place(x=320, y=250, width=100, height=25)
    # Botões para ações
    btn_club_vip = tk.Button(
        frame_principal,
        text="SOMAR CLUB VIP",
        font=font_poppins,
        command=lambda: somar_club_vip(resultados_label, soma_label),
        bg="#4CAF50",
        fg="white",
        padx=20,  # Padding horizontal
        pady=10,  # Padding vertical
        width=25,  # Largura do botão (em número de caracteres)
        height=1,  # Altura do botão (em número de linhas)
    )
    btn_club_vip.place(x=20, y=300, width=400, height=40)  # Posição e tamanho do botão

    btn_ggr_positivo = tk.Button(
        frame_principal,
        text="SOMAR GGR POSITIVO",
        font=font_poppins,
        command=lambda: somar_ggr_positivo(resultados_label, soma_label),
        bg="#2196F3",
        fg="white",
    )
    btn_ggr_positivo.place(x=20, y=350, width=400, height=40)

    btn_ggr_negativo = tk.Button(
        frame_principal,
        text="SOMAR GGR NEGATIVO",
        font=font_poppins,
        command=lambda: somar_ggr_negativo(resultados_label, soma_label),
        bg="#2274F7",
        fg="white",
        padx=20,  # Padding horizontal
        pady=10,  # Padding vertical
        width=25,  # Largura do botão (em número de caracteres)
        height=1,  # Altura do botão (em número de linhas)
    )
    btn_ggr_negativo.place(x=20, y=400, width=400, height=40)

    btn_limpar = tk.Button(
    frame_principal,
    text="LIMPAR",
    font=font_poppins,
    command=lambda: limpar(resultados_label, soma_label),
    bg="#F44336",
    fg="white",
    padx=20,  # Padding horizontal
    pady=10,  # Padding vertical
    width=25,  # Largura do botão (em número de caracteres)
    height=1,  # Altura do botão (em número de linhas)
)
    btn_limpar.place(x=20, y=450, width=400, height=40)

    app.mainloop()

if __name__ == "__main__":
    criar_interface()

