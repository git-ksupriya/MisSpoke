import textwrap


def main() -> None:
    """Entry point for the LinguaLive bot4 prototype.

    For now this is a simple placeholder that documents the intended flows
    based on your Figma blueprint:

    - Landing / language selection
    - Main tutor interface with mic + conversation loop
    - Writing practice
    - Progress dashboard
    - Session summary
    """

    description = textwrap.dedent(
        """
        LinguaLive bot4 prototype
        -------------------------
        This is a scaffold for your conversational language tutor. Next steps:

        - Hook this CLI into your existing ConvAI / backend stack used in agorabot
        - Add endpoints or handlers for:
          * /tutor (main speaking/listening loop)
          * /writing (canvas or handwriting analysis)
          * /progress (user stats and streaks)
          * /summary (session wrap-up)
        """
    ).strip()

    print(description)


if __name__ == "__main__":
    main()
