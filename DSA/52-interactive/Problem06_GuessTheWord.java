import java.util.*;

public class Problem06_GuessTheWord {
    // Guess the Word (LC 843) - minimize guesses with match feedback
    static String secret = "acckzz";
    
    static int match(String a, String b) {
        int m = 0;
        for (int i = 0; i < a.length(); i++) if (a.charAt(i) == b.charAt(i)) m++;
        return m;
    }
    
    static void findSecretWord(String[] wordlist) {
        List<String> candidates = new ArrayList<>(Arrays.asList(wordlist));
        Random rand = new Random(42);
        for (int attempt = 0; attempt < 10 && !candidates.isEmpty(); attempt++) {
            String guess = candidates.get(rand.nextInt(candidates.size()));
            int matches = match(guess, secret); // oracle call
            System.out.println("Guess: " + guess + " matches=" + matches);
            if (matches == 6) { System.out.println("Found!"); return; }
            List<String> next = new ArrayList<>();
            for (String w : candidates) if (match(guess, w) == matches) next.add(w);
            candidates = next;
        }
    }
    
    public static void main(String[] args) {
        String[] words = {"acckzz","ccbazz","eiowzz","abcczz","aackzz","ccazzz"};
        findSecretWord(words);
    }
}
