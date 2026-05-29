import java.util.*;

public class Problem25_TournamentWinnerFinding {
    static int[] skill = {3, 7, 2, 8, 5, 1, 9, 4};
    
    // Oracle: who wins between player a and player b
    static int match(int a, int b) { return skill[a] > skill[b] ? a : b; }
    
    static int findWinner(int n) {
        List<Integer> players = new ArrayList<>();
        for (int i = 0; i < n; i++) players.add(i);
        while (players.size() > 1) {
            List<Integer> next = new ArrayList<>();
            for (int i = 0; i < players.size() - 1; i += 2)
                next.add(match(players.get(i), players.get(i + 1)));
            if (players.size() % 2 == 1) next.add(players.get(players.size() - 1));
            players = next;
        }
        return players.get(0);
    }
    
    public static void main(String[] args) {
        System.out.println("Winner: player " + findWinner(8) + " (skill=" + skill[findWinner(8)] + ")");
    }
}
