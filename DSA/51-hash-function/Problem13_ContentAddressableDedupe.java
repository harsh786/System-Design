import java.util.*;
import java.security.*;

public class Problem13_ContentAddressableDedupe {
    private Map<String, String> store = new HashMap<>(); // hash -> content

    public String store(String content) throws Exception {
        String hash = sha256(content);
        store.putIfAbsent(hash, content);
        return hash;
    }

    public String retrieve(String hash) {
        return store.get(hash);
    }

    public boolean isDuplicate(String content) throws Exception {
        return store.containsKey(sha256(content));
    }

    private String sha256(String input) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] digest = md.digest(input.getBytes());
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        Problem13_ContentAddressableDedupe sol = new Problem13_ContentAddressableDedupe();
        String h1 = sol.store("hello world");
        String h2 = sol.store("hello world");
        System.out.println("Same hash: " + h1.equals(h2)); // true
        System.out.println("Is duplicate: " + sol.isDuplicate("hello world")); // true
        System.out.println("Content: " + sol.retrieve(h1));
    }
}
