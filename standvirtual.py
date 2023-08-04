import threading
import requests
from stem import Signal
from stem.control import Controller
from bs4 import BeautifulSoup
import csv
import time
import tkinter as tk
from tkinter import messagebox


TOR_PROXY_HOST = '127.0.0.1'
TOR_PROXY_PORT = 9150
TOR_CONTROL_PORT = 9151

current_ip = None  # Variável global para armazenar o endereço IP atual
stop_scraping = False  # Variável de controlo para parar o scraper

#função para criar o url com base no nome da marca do veículo, funciona também com o modelo do veículo
def get_search_url(brand_name):
    base_url = 'https://www.standvirtual.com/'
    search_url = base_url + 'carros/' + brand_name.lower().replace(' ', '-') + '/'
    return search_url

#função principal do scraping - inicia a pesquisa
def start_scraping(brand_name):
    search_url = get_search_url(brand_name)
    list_page_url = search_url

    data_list = []

    while list_page_url:
        renew_tor_identity()  # Renova o IP antes de cada página
        get_current_ip()
        chat_box2.insert(tk.END, f"A Aceder á página: {list_page_url}\n")
        chat_box2.see(tk.END)
        data, list_page_url = scrape_list_page(list_page_url)
        data_list.extend(data)

        if list_page_url is None:
            chat_box2.insert(tk.END, "Scraping concluído.\n")
            chat_box2.see(tk.END)
            break

    return data_list

def make_tor_request(url):
    session = requests.session()
    session.proxies = {'http': 'socks5h://{}:{}'.format(TOR_PROXY_HOST, TOR_PROXY_PORT),
                       'https': 'socks5h://{}:{}'.format(TOR_PROXY_HOST, TOR_PROXY_PORT)}
    return session.get(url)

def get_current_ip():
    response = make_tor_request('https://api.ipify.org')
    current_ip = response.text.strip()
    chat_box.insert(tk.END, f"Endereço de IP atual: {current_ip}\n")
    chat_box.see(tk.END)

def renew_tor_identity():
    global current_ip
    chat_box.insert(tk.END, "A tentar renovar o IP...\n")
    chat_box.see(tk.END)# sempre que é feito um print na chatbox é feito o scroll para baixo (acompanha o texto)
    time.sleep(2)
    if current_ip:
        chat_box.insert(tk.END, f"Endereço de IP anterior: {current_ip}\n")
        chat_box.see(tk.END)# sempre que é feito um print na chatbox é feito o scroll para baixo (acompanha o texto)
    with Controller.from_port(address=TOR_PROXY_HOST, port=TOR_CONTROL_PORT) as controller:
        controller.authenticate()
        controller.signal(Signal.NEWNYM)
    response = make_tor_request('https://api.ipify.org')
    current_ip = response.text.strip()
    chat_box.insert(tk.END, f"Novo endereço de IP: {current_ip}\n")
    chat_box.see(tk.END)# sempre que é feito um print na chatbox é feito o scroll para baixo (acompanha o texto)

#função que seleciona o próximo carro(link) a ser visitado
def scrape_list_page(url):
    renew_tor_identity()  # Renova o IP antes de pedido
    response = make_tor_request(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    data_list = []

    car_links = soup.select('article.ooa-j8iifw.evg565y0 a')
    for link in car_links:
        car_url = link['href']
        if stop_scraping:
            break
        chat_box2.insert(tk.END, f"A Aceder ao URL: {car_url}\n")
        chat_box2.see(tk.END)
        data = scrape_inner_page(car_url)
        data_list.append(data)

    next_page_link = soup.find('a', class_='next')
    if next_page_link:
        next_page_url = next_page_link['href']
    else:
        next_page_url = None

    save_data_to_csv(data_list)

    return data_list, next_page_url

#função para ir retirar ao html a informação que nos é necessária sobre o veículo
def scrape_inner_page(url):
    renew_tor_identity()  # Renova o IP antes de pedido
    response = make_tor_request(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    data = {}

    data['URL'] = url

    name_element = soup.find('h1', class_='offer-title')
    if name_element:
        vehicle_name = name_element.text.strip()
        vehicle_name = vehicle_name.replace('Poucos KMs', '')
        vehicle_name = vehicle_name.replace('Com garantia', '')
        vehicle_name = vehicle_name.replace('Sem garantia', '')
        data['Nome'] = vehicle_name.strip()
    else:
        data['Nome'] = 'Informacao nao disponivel'

    fuel_element = soup.find('span', class_='offer-params__label', string='Combustível')
    if fuel_element:
        fuel_value = fuel_element.find_next('div', class_='offer-params__value')
        data['Combustivel'] = fuel_value.text.strip()
    else:
        data['Combustivel'] = 'Informacao nao disponivel'

    mileage_element = soup.find('span', class_='offer-params__label', string='Quilómetros')
    if mileage_element:
        mileage_value = mileage_element.find_next('div', class_='offer-params__value')
        mileage_text = mileage_value.text.strip().replace(' km', '')
        data['Quilometragem'] = mileage_text
    else:
        data['Quilometragem'] = 'Informacao nao disponivel'

    registration_element = soup.find('span', class_='offer-params__label', string='Ano')
    if registration_element:
        registration_value = registration_element.find_next('div', class_='offer-params__value')
        data['Ano de matricula'] = registration_value.text.strip()
    else:
        data['Ano de matricula'] = 'Informacao nao disponivel'

    price_element = soup.find('span', class_='offer-price__number')
    if price_element:
        price_text = price_element.text.strip().replace('        EUR', '')
        data['Preco'] = price_text
    else:
        data['Preco'] = 'Informacao nao disponivel'

    seller_element = soup.find("span", {"class": "seller-phones__button"})
    if seller_element:
        data_id = seller_element.get("data-id")
        base = 'https://www.standvirtual.com/ajax/misc/contact/multi_phone/'
        full_phone_request = base + data_id + '/0/'
        response = make_tor_request(full_phone_request)
        if response.status_code == 200:
            phone_data = response.json()
            numero_correto = phone_data['value']
            data['Contato do vendedor'] = numero_correto
        else:
            data['Contato do vendedor'] = 'Informacao nao disponivel'
    else:
        data['Contato do vendedor'] = 'Informacao nao disponivel'

    return data

#função que salva os dados do scraper dentro de um ficheiro csv ("dados_carros.csv") - adiciona informação, não substitui informação
def save_data_to_csv(data_list):
    with open('dados_carros.csv', 'a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=data_list[0].keys())
        if file.tell() == 0:
            writer.writeheader()
        writer.writerows(data_list)

def on_start_button_click():
    global stop_scraping  # Define a variável de controlo como global
    brand_name = entry.get().strip()
    if brand_name:
        start_button.config(state=tk.DISABLED)
        stop_button.config(state=tk.NORMAL)

        stop_scraping = False  # Define a variável de controlo como False (continuar)

        thread = threading.Thread(target=start_scraping_thread, args=(brand_name,))
        thread.start()
    else:
        messagebox.showerror('Erro', 'Insira uma marca de carro válida.')

def on_stop_button_click():
    global stop_scraping  # Define a variável de controlo como global
    stop_button.config(state=tk.DISABLED)
    stop_scraping = True  # Define a variável de controlo como True (parar)

def start_scraping_thread(brand_name):
    data_list = start_scraping(brand_name)
    messagebox.showinfo("Concluído", "O Scraping de dados foi concluído com sucesso!")
    chat_box2.insert(tk.END, f"Scraping concluído! Total de carros guardados no ficheiro: {len(data_list)}\n")
    chat_box2.see(tk.END) # sempre que é feito um print na chatbox é feito o scroll para baixo (acompanha o texto)
    start_button.config(state=tk.NORMAL)

#criação do GUI
root = tk.Tk()
root.title('Scraping do StandVirtual')

root.config(bg="#2b2b2b")
frame = tk.Frame(root, bg="#2b2b2b")
frame.pack(pady=20)

label_font = ("Arial", 12, "bold")
label = tk.Label(frame, text='Marca do carro:', bg="#2b2b2b", fg="white", font=label_font)
label.grid(row=0, column=0, padx=10, pady=10, columnspan=2)

entry = tk.Entry(frame, width=30, bg="#464646", fg="white", insertbackground="white")
entry.grid(row=1, column=0, padx=10, pady=10, columnspan=2)

start_button = tk.Button(frame, text='Começar Scraping', command=on_start_button_click, bg="#464646", fg="white", bd=0)
start_button.grid(row=2, column=0, padx=10, pady=10)

stop_button = tk.Button(frame, text='Parar Scraping', command=on_stop_button_click, state=tk.DISABLED, bg="#464646", fg="white", bd=0)
stop_button.grid(row=2, column=1, padx=10, pady=10)

chat_box = tk.Text(root, height=10, width=100, bg="black", fg="#41ca00")  # Aumenta a text box
chat_box.pack(pady=10)

chat_box2 = tk.Text(root, height=10, width=100, bg="black", fg="#41ca00")  # Aumenta a text box
chat_box2.pack(pady=10)

footer_label = tk.Label(root, text="Rúben Rocha • Diogo Santos • Pedro Leite", bg="#2b2b2b", fg="white")
footer_label.pack(pady=1)

footer_label = tk.Label(root, text="ISTEC • Instituto Superior de Tecnologias Avançadas", bg="#2b2b2b", fg="white")
footer_label.pack(pady=1)

root.mainloop()