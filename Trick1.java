

import java.util.Scanner;
import java.util.Random;

class Card {
    private byte suit; // 1=Spades, 2=Clubs, 3=Hearts, 4=Diamonds
    private byte rank; // 1-13

    public Card(byte rank, byte suit) {
        this.rank = rank;
        this.suit = suit;
    }

    public void display() {
        String suitSymbol = switch (suit) {
            case 1 -> "\u2660"; // Spades
            case 2 -> "\u2663"; // Clubs
            case 3 -> "\u2665"; // Hearts
            case 4 -> "\u2666"; // Diamonds
            default -> "?";
        };
        System.out.printf("%2d%s", rank, suitSymbol);
    }
}

class Deck {
    private Card[] cards;
    private static final int TOTAL_CARDS = 52;

    public Deck() {
        cards = new Card[TOTAL_CARDS];
        int index = 0;
        for (byte s = 1; s <= 4; s++) {
            for (byte r = 1; r <= 13; r++) {
                cards[index++] = new Card(r, s);
            }
        }
    }

    public void shuffle() {
        Random rand = new Random();
        for (int i = cards.length - 1; i > 0; i--) {
            int j = rand.nextInt(i + 1);
            Card temp = cards[i];
            cards[i] = cards[j];
            cards[j] = temp;
        }
    }

    public Card getCard(int index) {
        return cards[index];
    }
}

public class Trick1 {
    private Card[][] board;
    private Card[] pile;
    private static final int ROWS = 7;
    private static final int COLS = 3;
    private static final int TOTAL_CARDS = 21;
    private static final int CHOSEN_CARD_INDEX = TOTAL_CARDS / 2;

    public Trick1(Deck deck) {
        pile = new Card[TOTAL_CARDS];
        for (int i = 0; i < TOTAL_CARDS; i++) {
            pile[i] = deck.getCard(i);
        }
        board = new Card[ROWS][COLS];
    }

    public void assignBoard() {
        int index = 0;
        for (int r = 0; r < ROWS; r++) {
            for (int c = 0; c < COLS; c++) {
                board[r][c] = pile[index++];
            }
        }
    }

    public void printBoard() {
        System.out.println("\nCurrent Board:");
        System.out.println("Col 1\tCol 2\tCol 3");
        for (int r = 0; r < ROWS; r++) {
            for (int c = 0; c < COLS; c++) {
                board[r][c].display();
                System.out.print("\t");
            }
            System.out.println();
        }
    }

    public void sandwich(int chosenCol) {
        int middleCol = chosenCol - 1;
        int leftCol = (middleCol + 1) % COLS;
        int rightCol = (middleCol + 2) % COLS;

        int index = 0;
        for (int r = 0; r < ROWS; r++) pile[index++] = board[r][leftCol];
        for (int r = 0; r < ROWS; r++) pile[index++] = board[r][middleCol];
        for (int r = 0; r < ROWS; r++) pile[index++] = board[r][rightCol];

        assignBoard();
    }

    public Card getChosenCard() {
        return pile[CHOSEN_CARD_INDEX];
    }

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        while (true) {
            Deck deck = new Deck();
            deck.shuffle();
            Trick1 trick = new Trick1(deck);
            trick.assignBoard();

            for (int round = 0; round < 3; round++) {
                trick.printBoard();
                System.out.print("Enter the column of your card (1/2/3): ");
                int col = scanner.nextInt();
                trick.sandwich(col);
            }

            System.out.print("\nThe card you chose is: ");
            trick.getChosenCard().display();
            System.out.println("\nPlay again? (y/n): ");
            char choice = scanner.next().toLowerCase().charAt(0);
            if (choice == 'n') break;
        }
        scanner.close();
    }
}

