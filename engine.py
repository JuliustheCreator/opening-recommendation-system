import pandas as pd
import sys
import requests
from chessdotcom import get_player_stats, get_player_game_archives
import chess.pgn
from io import StringIO
import scipy
from scipy.spatial import distance

'''
Preparing LiChess Dataframe:
    Will Be Used To Compare Openings With Respect To Rating (Collaborate-Based Filtering)
'''
    
username = input("Input Player Name: ")

#Chooses Highest Rating Between Rapid and Blitz
def get_player_rating(username):
    try:
        playerinfo = get_player_stats(username).json
    except:
        print("User Not Found.")
        return None

    timecontrols = ['chess_rapid', 'chess_blitz']
    ratings = []

    for timecontrol in timecontrols:
        ratings.append(playerinfo['stats'][timecontrol]['last']['rating'])
    if ratings[0] > ratings[1]:
        return ratings[0]
    return ratings[1]


'''
The "new" variable is true if the player has not played longer than 3 months.
If the player is "new" then bullet games will be used.
'''

new = False

#Retrives Last 6 Months of Games Played; Checks To See if Player is New
def get_player_games(username):
    all_games = []
    games = get_player_game_archives(username).json
    months_played = len(games['archives'])
    if months_played < 6:
        urls = games['archives']
        if months_played < 3:
            new = True
    else:
        urls = games['archives'][-6:]

    for url in urls:
        monthly_games = requests.get(url).json()
        all_games.append(monthly_games)
    return all_games


#Grabs ECO (Opening ID) From PGN
def get_ECO(pgn):
    pgn = StringIO(pgn)
    game = chess.pgn.read_game(pgn)
    ECO = game.headers['ECO']
    return ECO

#Grabs FEN from Game
def get_FEN(game):
    FEN = game['fen']
    return FEN

#Grabs Side (White or Black): 0 for Black, 1 for White
def get_side(game):
    side = game['white']['username']
    if side == username:
        return 'white'
    return 'black'

#Checks If Player Won
def check_for_win(game, side):
    if game[side]['result'] == 'win':
        return 1
    return 0
    

#Grabs Game Variation & Time Control
def get_variation(game):
    time_control = game['time_class']
    variation = game['rules']
    #Variation should be "Chess" for Normal Games
    return time_control, variation

#Grabs Opening Name from Game
def get_opening_name(pgn):
    pgn = StringIO(pgn)
    game = chess.pgn.read_game(pgn)
    ECO_url = game.headers['ECOUrl']
    #Grabbing Substring (Contains Opening Name) from ECO Url 
    opening_name = ECO_url[31:]
    return opening_name.replace('-',' ')


#Collecting All Recently Played Openings
white_eco = []
white_fen = []
white_result = []
white_names = []

black_fen = []
black_eco = []
black_result = []
black_names = []

try:
    get_player_games(username)
except:
    print("User Not Found.")
    sys.exit()

all_games = get_player_games(username)
for monthly_games in all_games:
    for game in monthly_games['games']:
        if not new:
            if get_variation(game)[0] == 'bullet' or get_variation(game)[1] != 'chess':
                continue
        if get_side(game) == 'white':
            white_eco.append(get_ECO(game['pgn']))
            white_fen.append(get_FEN(game))
            white_result.append(check_for_win(game, get_side(game)))
            white_names.append(get_opening_name(game['pgn']))
        else:
            black_eco.append(get_ECO(game['pgn']))
            black_fen.append(get_FEN(game))
            black_result.append(check_for_win(game, get_side(game)))
            black_names.append(get_opening_name(game['pgn']))

#Creating Seperate Dataframes Depending on if Player is Black or White
blackdf = pd.DataFrame()
whitedf = pd.DataFrame()

blackdf['Name'] = black_names
blackdf['ECO'] = black_eco
blackdf['FEN'] = black_fen
blackdf['Result'] = black_result

whitedf['Name'] = white_names
whitedf['ECO'] = white_eco
whitedf['FEN'] = white_fen
whitedf['Result'] = white_result

'''
Grabbing The User's Rating.
Only the User's Rating & The Openings They Play Will Be Taken Into Account in Choosing New Openings.
'''

user_rating = get_player_rating(username)


#Creating Dataframe using Lichess Game Dataset
lichessgames = pd.read_csv('games.csv')
lichessgames = lichessgames[['opening_name','opening_eco','white_rating','black_rating','winner']]

lichessgames.rename(columns = {'opening_name':'Name', 'opening_eco':'ECO'}, inplace = True)

#Creating Seperate Dataframes for White / Black Winners
grouped = lichessgames.groupby(lichessgames.winner)
whitelichessgames = grouped.get_group("white")
blacklichessgames = grouped.get_group("black")

whitelichessgames.reset_index(inplace = True, drop = True)
blacklichessgames.reset_index(inplace = True, drop = True)

whitelichessgames.drop(['black_rating', 'winner'], axis = 1, inplace = True)
blacklichessgames.drop(['white_rating', 'winner'], axis = 1, inplace = True)

#Adding Frequency Column to Player Dataframe
whitedf['Frequency'] = whitedf['Name'].map(whitedf['Name'].value_counts(normalize = True) * 100)
blackdf['Frequency'] = blackdf['Name'].map(blackdf['Name'].value_counts(normalize = True) * 100)

#Sorting by Most Played Openings
whitedf.sort_values(by = ['Frequency'], inplace = True, ascending = False)
blackdf.sort_values(by = ['Frequency'], inplace = True, ascending = False)

#Creating Win Rate Column for Player Dataframe
white_win_rate = whitedf.rename(columns = {"Result":"Count"}).groupby("Name").sum().reset_index()
black_win_rate = blackdf.rename(columns = {"Result":"Count"}).groupby("Name").sum().reset_index()

white_win_rate = pd.DataFrame(white_win_rate)
black_win_rate = pd.DataFrame(black_win_rate)

white_win_rate.sort_values(by = ['Frequency'], inplace = True, ascending = False)
black_win_rate.sort_values(by = ['Frequency'], inplace = True, ascending = False)

#Deleting Duplicate Openings in Player Dataframe
whitedf.drop_duplicates(subset = 'Name', inplace = True)
blackdf.drop_duplicates(subset = 'Name', inplace = True)

#Adding on Win Rate Column
white_win_rate = list(white_win_rate['Count'])
black_win_rate = list(black_win_rate['Count'])