import java.util.*;

/**
 * Problem 38: Design Authentication Manager
 * 
 * API Contract:
 * - generate(tokenId, currentTime): Generate token expiring at currentTime + TTL
 * - renew(tokenId, currentTime): Renew unexpired token
 * - countUnexpiredTokens(currentTime): Count active tokens
 * 
 * Complexity: O(n) for count (can be O(1) with cleanup), O(1) for others
 * Data Structure: HashMap<tokenId, expiryTime>
 * 
 * Production Analogy: JWT/session token management, OAuth2 refresh tokens,
 * API key expiration, distributed session stores
 */
public class Problem38_DesignAuthenticationManager {

    static class AuthenticationManager {
        private int ttl;
        private Map<String, Integer> tokens; // tokenId -> expiry time

        public AuthenticationManager(int timeToLive) {
            ttl = timeToLive;
            tokens = new HashMap<>();
        }

        public void generate(String tokenId, int currentTime) {
            tokens.put(tokenId, currentTime + ttl);
        }

        public void renew(String tokenId, int currentTime) {
            if (tokens.containsKey(tokenId) && tokens.get(tokenId) > currentTime) {
                tokens.put(tokenId, currentTime + ttl);
            }
        }

        public int countUnexpiredTokens(int currentTime) {
            int count = 0;
            for (int expiry : tokens.values()) {
                if (expiry > currentTime) count++;
            }
            return count;
        }
    }

    public static void main(String[] args) {
        AuthenticationManager am = new AuthenticationManager(5);
        am.generate("a", 1); // expires at 6
        assert am.countUnexpiredTokens(6) == 0; // expired at exactly 6
        am.generate("b", 2); // expires at 7
        assert am.countUnexpiredTokens(6) == 1; // b still valid
        am.renew("b", 6);   // renew -> expires at 11
        assert am.countUnexpiredTokens(7) == 1;
        am.renew("a", 7);   // a already expired, no-op
        assert am.countUnexpiredTokens(10) == 1;
        assert am.countUnexpiredTokens(11) == 0;

        System.out.println("All tests passed!");
    }
}
