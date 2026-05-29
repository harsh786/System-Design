import java.util.*;

public class Problem10_EncodeAndDecodeTinyURL {
    private Map<String, String> codeToUrl = new HashMap<>();
    private Map<String, String> urlToCode = new HashMap<>();
    private static final String CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    private Random rand = new Random();

    public String encode(String longUrl) {
        if (urlToCode.containsKey(longUrl)) return "http://tiny/" + urlToCode.get(longUrl);
        String code;
        do { StringBuilder sb = new StringBuilder(); for (int i = 0; i < 6; i++) sb.append(CHARS.charAt(rand.nextInt(62))); code = sb.toString(); }
        while (codeToUrl.containsKey(code));
        codeToUrl.put(code, longUrl);
        urlToCode.put(longUrl, code);
        return "http://tiny/" + code;
    }

    public String decode(String shortUrl) {
        return codeToUrl.get(shortUrl.substring(12));
    }

    public static void main(String[] args) {
        Problem10_EncodeAndDecodeTinyURL sol = new Problem10_EncodeAndDecodeTinyURL();
        String encoded = sol.encode("https://leetcode.com/problems/design-tinyurl");
        System.out.println("Encoded: " + encoded);
        System.out.println("Decoded: " + sol.decode(encoded));
    }
}
