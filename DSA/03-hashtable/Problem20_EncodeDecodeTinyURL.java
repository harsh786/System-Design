import java.util.*;

/**
 * Problem 20: Encode and Decode TinyURL
 * Design a URL shortening service.
 *
 * Approach: HashMap for bidirectional mapping. Generate random 6-char code.
 *
 * Time Complexity: O(1) for encode/decode
 * Space Complexity: O(n) for stored URLs
 *
 * Production Analogy: This IS TinyURL/bit.ly. Production adds distributed ID generation,
 * base62 encoding, and consistent hashing for horizontal scaling.
 */
public class Problem20_EncodeDecodeTinyURL {
    private Map<String, String> codeToUrl = new HashMap<>();
    private Map<String, String> urlToCode = new HashMap<>();
    private static final String CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    private Random rand = new Random();

    public String encode(String longUrl) {
        if (urlToCode.containsKey(longUrl)) return "http://tinyurl.com/" + urlToCode.get(longUrl);
        String code;
        do {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 6; i++) sb.append(CHARS.charAt(rand.nextInt(CHARS.length())));
            code = sb.toString();
        } while (codeToUrl.containsKey(code));
        codeToUrl.put(code, longUrl);
        urlToCode.put(longUrl, code);
        return "http://tinyurl.com/" + code;
    }

    public String decode(String shortUrl) {
        String code = shortUrl.replace("http://tinyurl.com/", "");
        return codeToUrl.get(code);
    }

    public static void main(String[] args) {
        Problem20_EncodeDecodeTinyURL sol = new Problem20_EncodeDecodeTinyURL();
        String url = "https://leetcode.com/problems/design-tinyurl";
        String encoded = sol.encode(url);
        System.out.println(encoded);
        System.out.println(sol.decode(encoded)); // original url
        System.out.println(sol.encode(url).equals(encoded)); // true - same encoding
    }
}
