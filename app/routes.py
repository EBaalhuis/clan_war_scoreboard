from flask import render_template
from app import app
import requests
from bs4 import BeautifulSoup
TOURNAMENT_ID = "5505"


class Player:
    def __init__(self, name, team):
        self.name = name
        self.team = team
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
                player1 = [p for p in players if p.name == player1_name][0]
                player2 = [p for p in players if p.name == player2_name][0]

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


@app.route('/')
@app.route('/index')
def index():
    players = get_players()
    teams = get_teams(players)
    process_rounds(players)
    nr_rounds = len(players[0].opponents)

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
                    opposing_team = player.opponents[round].team
                    done_teams.add(opposing_team)
                    row = [player.name, player.results[round], "-",
                           player.opponents[round].results[round], player.opponents[round].name]
                    rows.append(row)
                    if player.results[round] == "1":
                        total_wins += 1
                    elif player.results[round] == "0":
                        total_losses += 1
            header_row = [team, total_wins, "-", total_losses, opposing_team]
            rows.insert(0, header_row)
            round_data.append(rows)
        data.append(round_data)
    return render_template('index.html', data=data, nr_rounds=nr_rounds)
