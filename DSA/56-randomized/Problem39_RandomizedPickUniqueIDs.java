import java.util.*;

public class Problem39_RandomizedPickUniqueIDs {
    // Generate unique random IDs without collision
    Set<String> used = new HashSet<>();
    Random rand = new Random();

    public String generateId(int length) {
        String chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
        while (true) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < length; i++) sb.append(chars.charAt(rand.nextInt(chars.length())));
            String id = sb.toString();
            if (used.add(id)) return id;
        }
    }

    public static void main(String[] args) {
        Problem39_RandomizedPickUniqueIDs gen = new Problem39_RandomizedPickUniqueIDs();
        for (int i = 0; i < 10; i++) System.out.println(gen.generateId(8));
    }
}
