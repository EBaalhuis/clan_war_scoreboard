from flask import render_template
from app import app
import requests
import csv
from bs4 import BeautifulSoup

TOURNAMENT_ID = "5676"
SILVER_TOURNAMENT_ID = "5684"
SWISS_TABLES = 54
SWISS_ROUNDS = 5


class Player:
    def __init__(self, name, team):
        self.name = name
        self.team = team
        self.discord = ""
        self.decklist = ""
        self.clan = ""
        self.opponents = []
        self.results = []


def get_players(tournament_id):
    players = []
    url = "https://thelotuspavilion.com/tournaments/" + tournament_id + "/scores"
    response = requests.get(url)
    if response.status_code == 200:
        # Ugly way to remove LP drop icon, beautifulsoup cant handle it for some reason.
        # Maybe because LP gives double </span>
        fixed_text = response.text.replace('<span class="icon-droplet tooltip drop-color" data-tooltip="This player was dropped<br>from the tournament."></span>\n'
                    '                    </span>',
                     "")

        soup = BeautifulSoup(fixed_text, 'html.parser')
        table = soup.find("table", {"class": "fullwidth striped"})
        table_body = table.find('tbody')
        rows = table_body.find_all('tr', recursive=False)
        for row in rows:
            cols = row.find_all('td')
            cols = [ele.text.strip() for ele in cols]
            player = cols[1].split('\n')[0]
            if player.split(" ")[0] == "BYE":
                continue
            team = cols[1].split('\n')[1]
            players.append(Player(player, team))

        return players
    else:
        print("error requesting scoreboard page from LP")


def find_player_by_name(players, name):
    if name == "BYE":
        return Player(name, "BYE_TEAM")
    else:
        return [p for p in players if p.name.lower() == name.lower()][0]


def process_rounds(players, tournament_id):
    url = "https://thelotuspavilion.com/tournaments/" + tournament_id + "/games"
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
                player1 = find_player_by_name(players, player1_name)
                player2 = find_player_by_name(players, player2_name)

                player1.opponents.append(player2)
                player2.opponents.append(player1)
                if result == '10 – 1' or result == '10 – 0':  # watch out: the dash is not a minus
                    player1.results.append("1")
                    player2.results.append("0")
                elif result == '1 – 10' or result == '0 – 10':  # watch out: the dash is not a minus
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
    # this block was for season 1 when the source spreadsheets were different (had to link name to discord first)
    # with open("season2-name-discord.csv", mode='r') as file:
    #     reader = csv.reader(file)
    #     for row in reader:
    #         csv_name = row[0]
    #         discord = row[1]
    #         if len([p for p in players if p.name.lower() == csv_name.lower()]) == 0:
    #             print("Name not found in LP: ", csv_name)
    #         else:
    #             [p for p in players if p.name.lower() == csv_name.lower()][0].discord = discord

    for p in players:
        p.discord = p.name


def process_decklist_string(s):
    # result = string[29:]  # remove google redirect part at the start -- not used for S2
    # result = result[:result.find("&sa=")]  # remove google redirect part at the end -- not used for S2
    result = s.replace("%3D", "=").replace("%26", "&")  # replace symbols that don't copy well
    return result


def add_decklists(players, cups=False):
    if cups:
        file_name = "season2_name_deck_cups.csv"
    else:
        file_name = "season2_name_deck.csv"
    with open(file_name, mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            discord = row[0].split('#')[0].lower().strip()
            clan = row[1]
            decklist = process_decklist_string(row[2])
            if len([p for p in players if p.discord.split('#')[0].lower().strip() == discord]) == 0:
                pass
                # print("Discord handle not found in players: ", discord)
                # print([p.discord.lower() for p in players])
            else:
                [p for p in players if p.discord.split('#')[0].lower().strip() == discord][0].decklist = decklist
                [p for p in players if p.discord.split('#')[0].lower().strip() == discord][0].clan = clan


def generate_swiss_table(players, teams, nr_rounds):
    data = []
    for round in reversed(range(nr_rounds)):
        done_teams = set()
        round_data = []
        for team in teams:
            if team in done_teams:
                continue
            rows = []
            done_teams.add(team)
            team_wins = 0
            team_losses = 0
            for player in filter(lambda x: x.team == team, players):
                opponent = player.opponents[round]
                opposing_team = player.opponents[round].team
                done_teams.add(opposing_team)
                row = [player.name, player.results[round], "-",
                       opponent.results[round], opponent.name,
                       player.decklist, opponent.decklist,
                       player.clan, opponent.clan]
                rows.append(row)

                if player.results[round] == "1":
                    team_wins += 1
                elif player.results[round] == "0":
                    team_losses += 1
            header_row = [team, team_wins, "-", team_losses, opposing_team]
            rows.insert(0, header_row)
            round_data.append(rows)
        data.append(round_data)
    return data


def generate_cut_table(players, nr_rounds, swiss_rounds=SWISS_ROUNDS):
    data = []
    for round in reversed(range(nr_rounds)):
        round_data = []
        players_done = []
        for player in players:
            if len(player.opponents) <= swiss_rounds + round:  # player did not make it to this round
                continue
            if player in players_done:
                continue
            players_done.append(player)

            cut_round = round + swiss_rounds
            opponent = player.opponents[cut_round]
            if opponent.name == "BYE" or opponent.name.split(" ")[0] == "BYE":
                row = [player.name, player.results[cut_round], "-",
                       0, opponent.name,
                       player.decklist, "",
                       player.clan, "",
                       player.team, ""]
            else:
                players_done.append(opponent)
                row = [player.name, player.results[cut_round], "-",
                       opponent.results[cut_round], opponent.name,
                       player.decklist, opponent.decklist,
                       player.clan, opponent.clan,
                       player.team, opponent.team]
            round_data.append(row)
        data.append(round_data)
    return data


def get_summary(players, teams, silver_players):
    # Gold cup bonus points
    gold_bonus = {}
    for team in teams:
        gold_bonus[team] = 0
    for player in players:
        if len(player.results) >= 10 and player.results[9] == "1":  # won the final
            gold_bonus[player.team] = 5
        elif len(player.results) >= 9 and player.results[8] == "1":  # made top 2
            gold_bonus[player.team] = max(gold_bonus[player.team], 3)
        elif len(player.results) >= 8 and player.results[7] == "1":  # made top 4
            gold_bonus[player.team] = max(gold_bonus[player.team], 2)
        elif len(player.results) >= 7 and player.results[6] == "1":  # made top 8
            gold_bonus[player.team] = max(gold_bonus[player.team], 1)

    # Silver cup bonus points
    silver_bonus = {}
    for team in teams:
        silver_bonus[team] = 0
    for player in silver_players:
        if len(player.results) == 4 and player.results[3] == "1":  # won silver cup
            silver_bonus[player.team] = 2

    score = {}
    played = {}
    for team in teams:
        score[team] = gold_bonus[team] + silver_bonus[team]
        played[team] = 0

    for player in players + silver_players:
        for res in player.results:
            if res != "?":
                played[player.team] += 1
            if res == "1":
                score[player.team] += 1

    return sorted([[team, score[team], played[team], gold_bonus[team], silver_bonus[team]] for team in teams],
                  key=lambda x: -x[1] + x[2] / 1000)


def generate_players_page(players, teams, nr_rounds):
    data = []
    for team in teams:
        rows = []
        team_wins = 0
        for player in players:
            if player.team == team:
                wins, losses = 0, 0
                for res in player.results:
                    if res == "1":
                        wins += 1
                    if res == "0":
                        losses += 1
                team_wins += wins
                row = [player.name, player.decklist, wins, losses, player.clan]
                rows.append(row)
        rows = sorted(rows, key=lambda x: -int(x[2]) + 0.1 * int(x[3]))
        header_row = [team, team_wins]
        rows.insert(0, header_row)
        data.append(rows)

    return data


@app.route('/')
@app.route('/index')
def index():
    players = get_players(TOURNAMENT_ID)
    teams = get_teams(players)
    process_rounds(players, TOURNAMENT_ID)
    nr_rounds_swiss = min([len(p.opponents) for p in players])
    add_discord_names(players)
    add_decklists(players)
    swiss_data = generate_swiss_table(players, teams, nr_rounds_swiss)

    # Gold cup
    add_decklists(players, cups=True)
    nr_rounds_cut = max(max([len(p.opponents) for p in players]) - SWISS_ROUNDS, 0)
    cut_data = generate_cut_table(players, nr_rounds_cut)

    # Silver cup, that is in a different LP tournament
    silver_players = get_players(SILVER_TOURNAMENT_ID)
    process_rounds(silver_players, SILVER_TOURNAMENT_ID)
    add_discord_names(silver_players)
    add_decklists(silver_players, cups=True)
    nr_rounds_silver_cut = max(max([len(p.opponents) for p in silver_players]), 0)
    silver_data = generate_cut_table(silver_players, nr_rounds_silver_cut, swiss_rounds=0)

    # Summary at the top of the page
    summary = get_summary(players, teams, silver_players)

    return render_template('index.html', swiss_data=swiss_data, cut_data=cut_data, nr_rounds_swiss=nr_rounds_swiss,
                           nr_rounds_cut=nr_rounds_cut, summary=summary, round_size=[32, 16, 8, 4, 2],
                           silver_data=silver_data, nr_rounds_silver_cut=nr_rounds_silver_cut,
                           silver_rounds=[16, 8, 4, 2])


@app.route('/players')
def players_page():
    players = get_players(TOURNAMENT_ID)
    teams = get_teams(players)
    process_rounds(players, TOURNAMENT_ID)
    nr_rounds = len(players[0].opponents)
    add_discord_names(players)
    add_decklists(players)
    data = generate_players_page(players, teams, nr_rounds)

    return render_template('players.html', data=data)
