import java.util.*;

public class Problem47_RandomizedBinarySearchTree {
    // Insert at root with probability 1/(size+1) for balanced BST
    static Random rand = new Random();
    static class Node { int key,size; Node l,r; Node(int k){key=k;size=1;} }
    static int size(Node n){return n==null?0:n.size;}
    static void fix(Node n){if(n!=null)n.size=1+size(n.l)+size(n.r);}

    static Node rotateRight(Node p){Node q=p.l;p.l=q.r;q.r=p;fix(p);fix(q);return q;}
    static Node rotateLeft(Node p){Node q=p.r;p.r=q.l;q.l=p;fix(p);fix(q);return q;}

    static Node insertRoot(Node t, int key) {
        if(t==null) return new Node(key);
        if(key<t.key){t.l=insertRoot(t.l,key);t=rotateRight(t);}
        else{t.r=insertRoot(t.r,key);t=rotateLeft(t);}
        fix(t); return t;
    }

    static Node insert(Node t, int key) {
        if(t==null) return new Node(key);
        if(rand.nextInt(size(t)+1)==0) return insertRoot(t,key);
        if(key<t.key) t.l=insert(t.l,key); else t.r=insert(t.r,key);
        fix(t); return t;
    }

    static void inorder(Node t){if(t!=null){inorder(t.l);System.out.print(t.key+" ");inorder(t.r);}}

    public static void main(String[] args) {
        Node root=null;
        for(int i=1;i<=10;i++) root=insert(root,i); // sequential insert stays balanced
        inorder(root); System.out.println("\nRoot: "+root.key+" Size: "+root.size);
    }
}
