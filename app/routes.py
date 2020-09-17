from flask import render_template
from app import app
import requests
import csv
from bs4 import BeautifulSoup
TOURNAMENT_ID = "5505"


class Player:
    def __init__(self, name, team):
        self.name = name
        self.team = team
        self.discord = ""
        self.decklist = ""
        self.clan = ""
        self.opponents = []
        self.results = []


def get_players():
    players = []
    url = "https://thelotuspavilion.com/tournaments/" + TOURNAMENT_ID + "/scores"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find("table", {"class": "fullwidth striped"})
        table_body = table.find('tbody')

        rows = table_body.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            player = cols[1].split('\n')[0]
            team = cols[1].split('\n')[1]
            players.append(Player(player, team))
            # print("Found player {} on team {}".format(player, team))

        return players
    else:
        print("error requesting scoreboard page from LP")


def process_rounds(players):
    url = "https://thelotuspavilion.com/tournaments/" + TOURNAMENT_ID + "/games"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find("table", {"class": "striped fullwidth"})

        rounds = table.find_all('tbody')
        for round in reversed(rounds):
            rows = round.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                cols = [ele.text.strip() for ele in cols]
                player1_name = cols[1].split('\n')[0]
                player2_name = cols[3].split('\n')[0]
                result = cols[2]
                player1 = [p for p in players if p.name.lower() == player1_name.lower()][0]
                player2 = [p for p in players if p.name.lower() == player2_name.lower()][0]

                player1.opponents.append(player2)
                player2.opponents.append(player1)
                if result == '10 – 1':
                    player1.results.append("1")
                    player2.results.append("0")
                elif result == '1 – 10':
                    player1.results.append("0")
                    player2.results.append("1")
                else:
                    player1.results.append("?")
                    player2.results.append("?")
    else:
        print("error requesting games page from LP")


def get_teams(players):
    teams = set()
    for p in players:
        teams.add(p.team)
    teams = list(teams)
    teams.sort()
    return teams


def add_discord_names(players):
    with open("name-discord.csv", mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            csv_name = row[0]
            discord = row[1]
            if len([p for p in players if p.name.lower() == csv_name.lower()]) == 0:
                print("Name not found in LP: ", csv_name)
            else:
                [p for p in players if p.name.lower() == csv_name.lower()][0].discord = discord


def process_decklist_string(string):
    result = string[29:]  # remove google redirect part at the start
    result = result[:result.find("&sa=")]  # remove google redirect part at the end
    result = result.replace("%3D", "=").replace("%26", "&")  # replace symbols that don't copy well
    return result


def add_decklists(players):
    with open("name-deck-pack5.csv", mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            discord = row[0].split('#')[0].lower().strip()
            clan = row[1]
            decklist = process_decklist_string(row[2])
            if len([p for p in players if p.discord.lower() == discord]) == 0:
                print("Discord handle not found in players: ", discord)
            else:
                [p for p in players if p.discord.lower() == discord][0].decklist = decklist
                [p for p in players if p.discord.lower() == discord][0].clan = clan


def generate_table(players, teams, nr_rounds):
    data = []
    for round in reversed(range(nr_rounds)):
        done_teams = set()
        round_data = []
        for team in teams:
            if team in done_teams:
                continue
            rows = []
            done_teams.add(team)
            total_wins = 0
            total_losses = 0
            for player in players:
                if player.team == team:
                    opponent = player.opponents[round]
                    opposing_team = player.opponents[round].team
                    done_teams.add(opposing_team)
                    row = [player.name + " (" + player.discord + ")", player.results[round], "-",
                           opponent.results[round], opponent.name + " (" + opponent.discord + ")",
                           player.decklist, opponent.decklist,
                           player.clan, opponent.clan]
                    rows.append(row)
                    if player.results[round] == "1":
                        total_wins += 1
                    elif player.results[round] == "0":
                        total_losses += 1
            header_row = [team, total_wins, "-", total_losses, opposing_team]
            rows.insert(0, header_row)
            round_data.append(rows)
        data.append(round_data)
    return data


def get_summary(players, teams):
    wins = {}
    played = {}
    for team in teams:
        wins[team] = 0
        played[team] = 0

    for player in players:
        for res in player.results:
            if res != "?":
                played[player.team] += 1
            if res == "1":
                wins[player.team] += 1

    return sorted([[team, wins[team], played[team]] for team in teams], key=lambda x: -x[1]+x[2]/1000)


@app.route('/')
@app.route('/index')
def index():
    players = get_players()
    teams = get_teams(players)
    process_rounds(players)
    nr_rounds = len(players[0].opponents)
    add_discord_names(players)
    add_decklists(players)
    data = generate_table(players, teams, nr_rounds)
    summary = get_summary(players, teams)

    return render_template('index.html', data=data, nr_rounds=nr_rounds, summary=summary)
