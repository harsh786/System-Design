import java.util.*;

/**
 * Problem 20: Rank Teams by Votes
 * 
 * Each voter ranks all teams. Sort teams by votes received at each position.
 * 
 * Approach: Count votes per position for each team, then custom sort.
 * Time Complexity: O(n*m + m*m*log(m)) where n=voters, m=teams
 * Space Complexity: O(m²)
 * 
 * Production Analogy: Multi-criteria ranking in search engines - primary sort by relevance,
 * secondary by recency, tertiary by popularity.
 */
public class Problem20_RankTeamsByVotes {
    
    public String rankTeams(String[] votes) {
        int teams = votes[0].length();
        int[][] count = new int[26][teams]; // count[char][position]
        
        for (String vote : votes) {
            for (int i = 0; i < vote.length(); i++) {
                count[vote.charAt(i) - 'A'][i]++;
            }
        }
        
        Character[] chars = new Character[teams];
        for (int i = 0; i < teams; i++) chars[i] = votes[0].charAt(i);
        
        Arrays.sort(chars, (a, b) -> {
            for (int i = 0; i < teams; i++) {
                if (count[a - 'A'][i] != count[b - 'A'][i])
                    return count[b - 'A'][i] - count[a - 'A'][i];
            }
            return a - b; // alphabetical tiebreaker
        });
        
        StringBuilder sb = new StringBuilder();
        for (char c : chars) sb.append(c);
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem20_RankTeamsByVotes sol = new Problem20_RankTeamsByVotes();
        
        System.out.println("Test 1: " + sol.rankTeams(new String[]{"ABC","ACB","ABC","ACB","ACB"})); // "ACB"
        System.out.println("Test 2: " + sol.rankTeams(new String[]{"WXYZ","XYZW"})); // "XWYZ"
        System.out.println("Test 3: " + sol.rankTeams(new String[]{"ZMNAGUEDSJYLBOPHRQICWFXTVK"})); // "ZMNAGUEDSJYLBOPHRQICWFXTVK"
        System.out.println("Test 4: " + sol.rankTeams(new String[]{"BCA","CAB","CBA","ABC","ACB","BAC"})); // "ABC"
    }
}
