import java.util.*;

public class Problem36_CountingSortForMaxBalloons {
    public static int maxNumberOfBalloons(String text) {
        int[] count = new int[26];
        for (char c : text.toCharArray()) count[c-'a']++;
        int min = count['b'-'a'];
        min = Math.min(min, count['a'-'a']);
        min = Math.min(min, count['l'-'a'] / 2);
        min = Math.min(min, count['o'-'a'] / 2);
        min = Math.min(min, count['n'-'a']);
        return min;
    }

    public static void main(String[] args) {
        System.out.println(maxNumberOfBalloons("nlaebolko")); // 1
        System.out.println(maxNumberOfBalloons("loonbalxballpoon")); // 2
    }
}
