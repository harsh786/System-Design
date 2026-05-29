import java.util.*;
import java.security.*;

public class Problem40_HashURLShortener {
    private Map<String, String> shortToLong = new HashMap<>();

    public String shorten(String url) throws Exception {
        MessageDigest md = MessageDigest.getInstance("MD5");
        byte[] digest = md.digest(url.getBytes());
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 4; i++) sb.append(String.format("%02x", digest[i]));
        String shortCode = sb.toString();
        shortToLong.put(shortCode, url);
        return "http://short/" + shortCode;
    }

    public String expand(String shortUrl) {
        return shortToLong.get(shortUrl.substring(13));
    }

    public static void main(String[] args) throws Exception {
        Problem40_HashURLShortener sol = new Problem40_HashURLShortener();
        String shortUrl = sol.shorten("https://www.example.com/very/long/path");
        System.out.println("Short: " + shortUrl);
        System.out.println("Expanded: " + sol.expand(shortUrl));
    }
}
