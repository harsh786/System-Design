import java.util.*;

public class Problem22_MastermindScore {
    static String secret = "RGBY";
    
    static int[] getScore(String guess) {
        int bulls = 0, cows = 0;
        int[] sCount = new int[26], gCount = new int[26];
        for (int i = 0; i < 4; i++) {
            if (guess.charAt(i) == secret.charAt(i)) bulls++;
            else { sCount[secret.charAt(i)-'A']++; gCount[guess.charAt(i)-'A']++; }
        }
        for (int i = 0; i < 26; i++) cows += Math.min(sCount[i], gCount[i]);
        return new int[]{bulls, cows};
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(getScore("RGYB"))); // [2,2]
        System.out.println(Arrays.toString(getScore("RGBY"))); // [4,0]
    }
}
