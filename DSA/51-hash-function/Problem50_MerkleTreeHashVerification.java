import java.util.*;
import java.security.*;

public class Problem50_MerkleTreeHashVerification {
    private String[] tree;
    private int leafCount;

    public Problem50_MerkleTreeHashVerification(String[] data) {
        leafCount = 1;
        while (leafCount < data.length) leafCount *= 2;
        tree = new String[2 * leafCount];
        Arrays.fill(tree, "");
        for (int i = 0; i < data.length; i++) tree[leafCount + i] = sha256(data[i]);
        for (int i = leafCount - 1; i >= 1; i--) tree[i] = sha256(tree[2*i] + tree[2*i+1]);
    }

    public String getRoot() { return tree[1]; }

    public List<String> getProof(int index) {
        List<String> proof = new ArrayList<>();
        int pos = leafCount + index;
        while (pos > 1) {
            proof.add(tree[pos ^ 1]); // sibling
            pos /= 2;
        }
        return proof;
    }

    public boolean verify(String data, int index, List<String> proof, String root) {
        String hash = sha256(data);
        int pos = leafCount + index;
        int proofIdx = 0;
        while (pos > 1) {
            String sibling = proof.get(proofIdx++);
            hash = (pos % 2 == 0) ? sha256(hash + sibling) : sha256(sibling + hash);
            pos /= 2;
        }
        return hash.equals(root);
    }

    private String sha256(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest(input.getBytes());
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception e) { throw new RuntimeException(e); }
    }

    public static void main(String[] args) {
        String[] data = {"tx1", "tx2", "tx3", "tx4"};
        Problem50_MerkleTreeHashVerification merkle = new Problem50_MerkleTreeHashVerification(data);
        System.out.println("Root: " + merkle.getRoot().substring(0, 16) + "...");
        List<String> proof = merkle.getProof(2);
        System.out.println("Proof size for index 2: " + proof.size());
        System.out.println("Verified: " + merkle.verify("tx3", 2, proof, merkle.getRoot())); // true
        System.out.println("Tampered: " + merkle.verify("tx3_fake", 2, proof, merkle.getRoot())); // false
    }
}
